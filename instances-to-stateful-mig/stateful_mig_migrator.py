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
import argparse
import re
import time
import typing
import uuid

import google.auth
import google.cloud.compute_v1 as compute_v1


instance_client = compute_v1.InstancesClient()
zone_operations_client = compute_v1.ZoneOperationsClient()
global_operations_client = compute_v1.GlobalOperationsClient()
images_client = compute_v1.ImagesClient()
disks_client = compute_v1.DisksClient()
region_disks_client = compute_v1.RegionDisksClient()
instance_templates_client = compute_v1.InstanceTemplatesClient()
instance_group_managers_client = compute_v1.InstanceGroupManagersClient()
region_operations_client = compute_v1.RegionOperationsClient()
region_instance_group_managers_client = compute_v1.RegionInstanceGroupManagersClient()


class StatefulMIGMigrator:
    def __init__(self, args: argparse.Namespace) -> None:
        self.project = args.project if args.project else google.auth.default()[1]
        self.source_instances = args.source_instances
        self.source_instance_zone = args.source_instance_zone
        self.mig_name = args.mig_name
        self.image_for_boot_disk = args.image_for_boot_disk

        self.base_instance_name = (
            args.base_instance_name
            if args.base_instance_name
            else self.source_instances[0]
        )

        self.zone = None
        self.region = None

        if args.regional:
            # If MIG is regional, then save only region part (ex. "us-central1-a" -> "us-central1")
            self.region = "-".join(self.source_instance_zone.split("-")[:-1])
        else:
            self.zone = self.source_instance_zone

    def _get_instance(self, instance_name, instance_zone) -> None:
        return instance_client.get(
            project=self.project, zone=instance_zone, instance=instance_name,
        )

    def _stop_instance(self, instance_name: str, instance_zone: str) -> None:
        operation = instance_client.stop_unary(
            project=self.project, zone=instance_zone, instance=instance_name,
        )

        self._wait_for_operation(operation, instance_zone)

    def _build_template_link(self, template_name: str) -> str:
        return f"projects/{self.project}/global/instanceTemplates/{template_name}"

    def _build_image_link(self, image_name: str) -> str:
        return f"projects/{self.project}/global/images/{image_name}"

    def _build_disk_link(self, disk_name: str, disk_zone: str) -> str:
        return f"projects/{self.project}/zones/{disk_zone}/disks/{disk_name}"

    def _build_region_disk_link(self, disk_name: str, disk_region: str) -> str:
        return f"projects/{self.project}/regions/{disk_region}/disks/{disk_name}"

    def _build_zone_link(self, zone: str) -> str:
        return f"https://www.googleapis.com/compute/v1/projects/{self.project}/zones/{zone}"

    def _parse_disk_zone_from_source(self, source: str) -> str:
        return re.search("/zones/(.*?)/", source).group(1)

    def _parse_disk_region_from_source(self, source: str) -> str:
        return re.search("/regions/(.*?)/", source).group(1)

    def _create_image_for_disk(self, disk: compute_v1.AttachedDisk) -> str:
        image_name = f"{disk.device_name}-image-{uuid.uuid4().hex[:6]}"

        operation = images_client.insert_unary(
            project=self.project,
            image_resource={"name": image_name, "source_disk": disk.source},
        )

        self._wait_for_operation(operation)

        return image_name

    def _create_empty_mig(self, template_name: str) -> None:
        if self.zone:
            operation = instance_group_managers_client.insert_unary(
                project=self.project,
                zone=self.zone,
                instance_group_manager_resource={
                    "target_size": 0,
                    "name": self.mig_name,
                    "instance_template": self._build_template_link(template_name),
                },
            )

            self._wait_for_operation(operation, self.zone)

        if self.region:
            operation = region_instance_group_managers_client.insert_unary(
                project=self.project,
                region=self.region,
                instance_group_manager_resource={
                    "target_size": 0,
                    "name": self.mig_name,
                    "instance_template": self._build_template_link(template_name),
                    # Set the instance redistribution type to NONE so that the MIG does not automatically redistribute instances across zones.
                    # (https://cloud.google.com/compute/docs/instance-groups/distributing-instances-with-regional-instance-groups#disabling_and_reenabling_proactive_instance_redistribution)
                    "update_policy": {"instance_redistribution_type": "NONE"},
                },
            )

            self._wait_for_operation(operation, zone=None, region=self.region)

    def _create_instance_template(self, disk_configs: typing.List[dict]) -> str:
        template_name = f"{self.base_instance_name}-template-{uuid.uuid4().hex[:6]}"

        operation = instance_templates_client.insert_unary(
            project=self.project,
            instance_template_resource={
                "name": template_name,
                "source_instance": self.base_instance.self_link,
                "source_instance_params": {"disk_configs": disk_configs},
            },
        )

        self._wait_for_operation(operation)

        return template_name

    def _add_instance_to_mig(
        self, instance_name: str, attached_disks, metadata
    ) -> None:
        if self.zone:
            operation = instance_group_managers_client.create_instances_unary(
                project=self.project,
                zone=self.zone,
                instance_group_manager=self.mig_name,
                instance_group_managers_create_instances_request_resource=compute_v1.InstanceGroupManagersCreateInstancesRequest(
                    instances=[
                        compute_v1.PerInstanceConfig(
                            name=instance_name,
                            preserved_state=compute_v1.PreservedState(
                                disks=attached_disks, metadata=metadata,
                            ),
                        )
                    ]
                ),
            )

            self._wait_for_operation(operation, self.zone)

            # Waiting while all instances in the MIG will be created
            while not all(
                instance.current_action
                != compute_v1.ManagedInstance.CurrentAction.CREATING.name
                for instance in instance_group_managers_client.list_managed_instances(
                    project=self.project,
                    zone=self.zone,
                    instance_group_manager=self.mig_name,
                )
            ):
                time.sleep(3)

        if self.region:
            operation = region_instance_group_managers_client.create_instances_unary(
                project=self.project,
                region=self.region,
                instance_group_manager=self.mig_name,
                region_instance_group_managers_create_instances_request_resource=compute_v1.RegionInstanceGroupManagersCreateInstancesRequest(
                    instances=[
                        compute_v1.PerInstanceConfig(
                            name=instance_name,
                            preserved_state=compute_v1.PreservedState(
                                disks=attached_disks, metadata=metadata,
                            ),
                        )
                    ]
                ),
            )

            self._wait_for_operation(operation, zone=None, region=self.region)

            # Waiting while all instances in the MIG will be created
            while not all(
                instance.current_action
                != compute_v1.ManagedInstance.CurrentAction.CREATING.name
                for instance in region_instance_group_managers_client.list_managed_instances(
                    project=self.project,
                    region=self.region,
                    instance_group_manager=self.mig_name,
                )
            ):
                time.sleep(3)

    def _wait_for_operation(
        self, operation: compute_v1.Operation, zone: str = None, region: str = None
    ) -> None:
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

    def _print_cleanup_commands(self) -> None:
        print("\nTo revert all changes, use this clean up commands:")

        self.created_artifacts.sort(key=lambda x: x["priority"])

        for artifact in self.created_artifacts:
            if artifact["key"] == "instance_template":
                print(f"* gcloud compute instance-templates delete {artifact['name']}")

            if artifact["key"] == "disk":
                print(f"* gcloud compute disks delete {artifact['name']}")

            if artifact["key"] == "mig":
                print(
                    f"* gcloud compute instance-groups managed delete {artifact['name']}"
                )

            if artifact["key"] == "image":
                print(f"* gcloud compute images delete {artifact['name']}")
        print()

    def migrate(self) -> None:
        self.created_artifacts = []

        try:
            script_start_time = time.time()
            self.base_instance = self._get_instance(
                self.base_instance_name, self.source_instance_zone
            )

            # Step 1. Stop all instances

            for instance_name in self.source_instances:
                instance = self._get_instance(instance_name, self.source_instance_zone)

                if instance.status != compute_v1.Instance.Status.TERMINATED.name:
                    print(f"Instance {instance.name} is not stopped. Stopping ...")

                    self._stop_instance(instance_name, self.source_instance_zone)

                    print(f"Instance {instance.name} stopped")
                    print("==========")

            # Step 2. Create an instance template from the base instance

            base_disk_configs = []

            for disk in self.base_instance.disks:
                if disk.boot:
                    if self.image_for_boot_disk:
                        print(
                            f"Creating disk image for boot image {disk.device_name} ..."
                        )
                        image_name = self._create_image_for_disk(disk)
                        print(f"Disk image {image_name} created")
                        print("==========")

                        self.created_artifacts.append(
                            {"key": "image", "name": image_name, "priority": 4}
                        )

                        base_disk_configs.append(
                            {
                                "device_name": disk.device_name,
                                "custom_image": self._build_image_link(image_name),
                                "instantiate_from": "CUSTOM_IMAGE",
                            }
                        )

                    continue

                # We should remove all disks (except boot disk) from template
                base_disk_configs.append(
                    {
                        "device_name": disk.device_name,
                        "instantiate_from": "DO_NOT_INCLUDE",
                    }
                )

            print("Creating base instance template ...")
            base_instance_template_name = self._create_instance_template(
                base_disk_configs
            )
            self.created_artifacts.append(
                {
                    "key": "instance_template",
                    "name": base_instance_template_name,
                    "priority": 2,
                }
            )
            print(f"Instance template {base_instance_template_name} created")
            print("==========")

            # Step 3. Create an empty MIG

            print(f"Creating empty MIG {self.mig_name}...")
            self._create_empty_mig(base_instance_template_name)
            self.created_artifacts.append(
                {"key": "mig", "name": self.mig_name, "priority": 1}
            )
            print(f"MIG {self.mig_name} created")
            print("==========")

            # Step 4. Add instances to MIG one by one

            for instance_name in self.source_instances:
                instance = self._get_instance(instance_name, self.source_instance_zone)

                new_disks_config = {}

                for disk in instance.disks:
                    # boot disk will be created from template
                    if disk.boot:
                        continue

                    new_disk_name = f"{disk.device_name}-{uuid.uuid4().hex[:6]}"

                    print(f"Creating disk {new_disk_name} from disk {disk.device_name}")
                    print("==========")

                    if self.zone:
                        disk_zone = self._parse_disk_zone_from_source(disk.source)

                        operation = disks_client.insert_unary(
                            project=self.project,
                            zone=disk_zone,
                            disk_resource={
                                "source_disk": self._build_disk_link(
                                    disk.device_name, disk_zone
                                ),
                                "name": new_disk_name,
                            },
                        )

                        self._wait_for_operation(operation, disk_zone)

                        self.created_artifacts.append(
                            {"key": "disk", "name": new_disk_name, "priority": 3}
                        )

                        new_disks_config[
                            new_disk_name
                        ] = compute_v1.PreservedStatePreservedDisk(
                            source=self._build_disk_link(new_disk_name, disk_zone)
                        )

                    if self.region:
                        disk_region = self._parse_disk_region_from_source(disk.source)

                        disk_object = region_disks_client.get(
                            project=self.project,
                            region=disk_region,
                            disk=disk.device_name,
                        )

                        operation = region_disks_client.insert_unary(
                            project=self.project,
                            region=disk_region,
                            disk_resource={
                                "source_disk": self._build_region_disk_link(
                                    disk.device_name, disk_region
                                ),
                                "name": new_disk_name,
                                "replica_zones": disk_object.replica_zones,
                            },
                        )

                        self._wait_for_operation(
                            operation, zone=None, region=disk_region
                        )
                        self.created_artifacts.append(
                            {"key": "disk", "name": new_disk_name, "priority": 3}
                        )

                        new_disks_config[
                            new_disk_name
                        ] = compute_v1.PreservedStatePreservedDisk(
                            source=self._build_region_disk_link(
                                new_disk_name, disk_region
                            )
                        )

                metadata = []

                for item in instance.metadata.items:
                    metadata.append([item.key, item.value])

                new_instance_name = f"{instance_name}-{uuid.uuid4().hex[:6]}"

                print(f"Adding instance {new_instance_name} to {self.mig_name} MIG")
                print("==========\n")

                self._add_instance_to_mig(new_instance_name, new_disks_config, metadata)

            script_end_time = time.time()

            script_diff_time = script_end_time - script_start_time

            print(
                f"Migration successfully finished. Time spent: {int(script_diff_time)} seconds."
            )
            # Step 4. Print console commands for clean up

            # Clean source instances
            print(
                "Use the following command to delete the individual source instances:"
            )
            print(
                f'* gcloud compute instances delete {" ".join(self.source_instances)}'
            )

            self._print_cleanup_commands()

            print("Futher steps:")
            print(
                "- Configuring autohealing: https://cloud.google.com/compute/docs/tutorials/migrate-workload-to-stateful-mig#configuring_autohealing"
            )
            print("- Using a stateful policy instead of per-instance configurations:")
            print(
                "  https://cloud.google.com/compute/docs/tutorials/migrate-workload-to-stateful-mig#using_a_stateful_policy_instead_of_per-instance_configurations"
            )
            print("- Adding more VMs:")
            print(
                "  https://cloud.google.com/compute/docs/tutorials/migrate-workload-to-stateful-mig#adding_more_vms"
            )
        except Exception as err:
            print(f"Script failed during the execution. Reason: {err}")
            self._print_cleanup_commands()
