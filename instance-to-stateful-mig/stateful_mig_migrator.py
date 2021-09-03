# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import time
import uuid

import google.auth
import google.cloud.compute_v1 as compute_v1


instance_client = compute_v1.InstancesClient()
zone_operations_client = compute_v1.ZoneOperationsClient()
global_operations_client = compute_v1.GlobalOperationsClient()
images_client = compute_v1.ImagesClient()
disks_client = compute_v1.DisksClient()
instance_templates_client = compute_v1.InstanceTemplatesClient()
instance_group_managers_client = compute_v1.InstanceGroupManagersClient()
region_operations_client = compute_v1.RegionOperationsClient()
region_instance_group_managers_client = compute_v1.RegionInstanceGroupManagersClient()


class StatefulMIGMigrator:
    def __init__(self, args):
        self.project = args.project if args.project else google.auth.default()[1]

        self.source_instance_name = args.source_instance_name
        self.source_zone = args.source_zone

        self.mig_name = args.mig_name

        self.target_instance_name = (
            args.target_instance_name
            if args.target_instance_name
            else args.source_instance_name
        )

        self.target_zone = None
        self.target_region = None

        if args.regional:
            self.target_region = "-".join(self.source_zone.split("-")[:-1])
        else:
            self.target_zone = self.source_zone

        self.delete_source_instance = args.delete_source_instance

    def _get_source_instance(self):
        return instance_client.get(
            project=self.project,
            zone=self.source_zone,
            instance=self.source_instance_name,
        )

    def _stop_source_instance(self):
        operation = instance_client.stop(
            project=self.project,
            zone=self.source_zone,
            instance=self.source_instance_name,
        )

        self._wait_for_operation(operation, self.source_zone)

    def _delete_source_instance(self):
        operation = instance_client.delete(
            project=self.project,
            zone=self.source_zone,
            instance=self.source_instance_name,
        )

        self._wait_for_operation(operation, self.source_zone)

    def _build_template_link(self, template_name):
        return f"projects/{self.project}/global/instanceTemplates/{template_name}"

    def _build_image_link(self, image_name):
        return f"projects/{self.project}/global/images/{image_name}"

    def _create_image_for_disk(self, disk):
        image_name = f"{disk.device_name}-image-{uuid.uuid4().hex[:6]}"

        operation = images_client.insert(
            project=self.project,
            image_resource={"name": image_name, "source_disk": disk.source},
        )

        self._wait_for_operation(operation)

        return image_name

    def _create_empty_mig(self, template_name):
        if self.target_zone:
            operation = instance_group_managers_client.insert(
                project=self.project,
                zone=self.target_zone,
                instance_group_manager_resource={
                    "target_size": 0,
                    "name": self.mig_name,
                    "instance_template": self._build_template_link(template_name),
                },
            )

            self._wait_for_operation(operation, self.target_zone)

        if self.target_region:
            operation = region_instance_group_managers_client.insert(
                project=self.project,
                region=self.target_region,
                instance_group_manager_resource={
                    "target_size": 0,
                    "name": self.mig_name,
                    "instance_template": self._build_template_link(template_name),
                    "update_policy": {"instance_redistribution_type": "NONE"},
                },
            )

            self._wait_for_operation(operation, zone=None, region=self.target_region)

        time.sleep(3)

    def _create_instance_template(self, disk_configs):
        template_name = f"{self.source_instance_name}-template-{uuid.uuid4().hex[:6]}"

        operation = instance_templates_client.insert(
            project=self.project,
            instance_template_resource={
                "name": template_name,
                "source_instance": self.source_instance.self_link,
                "source_instance_params": {"disk_configs": disk_configs},
            },
        )

        self._wait_for_operation(operation)

        return template_name

    def _add_instance_to_mig(self):
        if self.target_zone:
            operation = instance_group_managers_client.create_instances(
                project=self.project,
                zone=self.target_zone,
                instance_group_manager=self.mig_name,
                instance_group_managers_create_instances_request_resource={
                    "instances": [{"name": self.target_instance_name}],
                },
            )

            self._wait_for_operation(operation, self.target_zone)

            while not all(
                instance.current_action
                != compute_v1.ManagedInstance.CurrentAction.CREATING
                for instance in instance_group_managers_client.list_managed_instances(
                    project=self.project,
                    zone=self.target_zone,
                    instance_group_manager=self.mig_name,
                )
            ):
                time.sleep(3)

        if self.target_region:
            operation = region_instance_group_managers_client.create_instances(
                project=self.project,
                region=self.target_region,
                instance_group_manager=self.mig_name,
                region_instance_group_managers_create_instances_request_resource={
                    "instances": [{"name": self.target_instance_name}]
                },
            )

            self._wait_for_operation(operation, zone=None, region=self.target_region)

            while not all(
                instance.current_action
                != compute_v1.ManagedInstance.CurrentAction.CREATING
                for instance in region_instance_group_managers_client.list_managed_instances(
                    project=self.project,
                    region=self.target_region,
                    instance_group_manager=self.mig_name,
                )
            ):
                time.sleep(3)

    def _wait_for_operation(self, operation, zone=None, region=None):
        while operation.status != compute_v1.Operation.Status.DONE:
            if zone:
                operation = zone_operations_client.wait(
                    operation=operation.name, project=self.project, zone=zone,
                )
            elif region:
                operation = region_operations_client.wait(
                    operation=operation.name, project=self.project, region=region
                )
            else:
                operation = global_operations_client.wait(
                    operation=operation.name, project=self.project,
                )

    def migrate(self):
        script_start_time = time.time()
        self.source_instance = self._get_source_instance()

        # Step 1. Stop instance if needed

        if self.source_instance.status != compute_v1.Instance.Status.TERMINATED:
            print(f"Instance {self.source_instance.name} is not stopped. Stopping ...")

            self._stop_source_instance()

            print(f"Instance {self.source_instance.name} stopped")
            print("==========")

        # Step 2. Create images for all disks

        disk_configs = []

        for disk in self.source_instance.disks:
            print(f"Creating image for disk {disk.device_name} ...")

            image_name = self._create_image_for_disk(disk)

            disk_configs.append(
                {
                    "device_name": disk.device_name,
                    "custom_image": self._build_image_link(image_name),
                    "instantiate_from": compute_v1.DiskInstantiationConfig.InstantiateFrom.CUSTOM_IMAGE,
                }
            )

            print(f"Disk image {image_name} generated")
            print("==========")

        # Step 3. Create an instance template

        print("Creating instance template ...")
        instance_template_name = self._create_instance_template(disk_configs)
        print(f"Instance template {instance_template_name} created")
        print("==========")

        # Step 4. Create an empty MIG

        print(f"Creating empty MIG {self.mig_name}...")
        self._create_empty_mig(instance_template_name)
        print(f"MIG {self.mig_name} created")
        print("==========")

        # Step 5. Delete source image if needed

        if self.delete_source_instance:
            print(f"Deleting source instance {self.source_instance_name}")
            self._delete_source_instance()
            print(f"Instance {self.source_instance_name} deleted")
            print("==========")

        # Step 6. Add instance to MIG

        print(f"Adding instance {self.target_instance_name} to {self.mig_name} ... ")
        self._add_instance_to_mig()
        print("Instance added ... ")
        print("==========")

        script_end_time = time.time()

        script_diff_time = script_end_time - script_start_time

        print(
            f"Migration successfully finished. Time spent: {int(script_diff_time)} seconds."
        )
