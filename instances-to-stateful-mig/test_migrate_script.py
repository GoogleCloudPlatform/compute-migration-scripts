import subprocess
import typing
import uuid

import google.auth
import google.cloud.compute_v1 as compute_v1

instance_client = compute_v1.InstancesClient()
operation_client = compute_v1.ZoneOperationsClient()
instance_group_managers_client = compute_v1.InstanceGroupManagersClient()
region_operations_client = compute_v1.RegionOperationsClient()
region_instance_group_managers_client = compute_v1.RegionInstanceGroupManagersClient()
region_disks_client = compute_v1.RegionDisksClient()

default_project_id = google.auth.default()[1]
default_zone = "us-central1-a"
default_region = "us-central1"
default_mig_name = "mig_name"
default_instance_name = "test-mig-instance"


def create_instance(instance_name: str, disks: typing.List[typing.Dict]) -> None:
    boot_disk_name = f"mig-boot-disk-{uuid.uuid4().hex[:10]}"
    data_disk_name = f"mig-data-disk-{uuid.uuid4().hex[:10]}"

    default_disks = [
        {
            "device_name": boot_disk_name,
            "initialize_params": {
                "disk_name": boot_disk_name,
                "source_image": "projects/debian-cloud/global/images/family/debian-10",
                "disk_size_gb": 10,
            },
            "auto_delete": True,
            "boot": True,
            "type_": "PERSISTENT",
        },
        {
            "device_name": data_disk_name,
            "initialize_params": {
                "disk_name": data_disk_name,
                "source_image": "projects/debian-cloud/global/images/family/debian-10",
                "disk_size_gb": 50,
            },
            "auto_delete": True,
            "type_": "PERSISTENT",
        },
    ]
    intance_create_request = compute_v1.InsertInstanceRequest(
        zone=default_zone,
        project=default_project_id,
        instance_resource={
            "name": instance_name,
            "disks": disks if disks else default_disks,
            "machine_type": f"zones/{default_zone}/machineTypes/n1-standard-1",
            "network_interfaces": [{"name": "global/networks/default"}],
        },
    )

    operation = instance_client.insert_unary(request=intance_create_request)
    while operation.status != compute_v1.Operation.Status.DONE:
        operation = operation_client.wait(
            operation=operation.name, zone=default_zone, project=default_project_id
        )


def delete_instance(instance_name: str) -> None:
    operation = instance_client.delete_unary(
        project=default_project_id, zone=default_zone, instance=instance_name
    )

    while operation.status != compute_v1.Operation.Status.DONE:
        operation = operation_client.wait(
            operation=operation.name, zone=default_zone, project=default_project_id
        )


def test_regional_migration(capsys: typing.Any) -> None:
    source_instance_name = default_instance_name + "-" + uuid.uuid4().hex[:10]
    boot_disk_name = f"mig-boot-disk-{uuid.uuid4().hex[:10]}"
    data_disk_name = f"mig-data-disk-{uuid.uuid4().hex[:10]}"

    mig_name = "mig-" + uuid.uuid4().hex[:10]

    operation = region_disks_client.insert_unary(
        project=default_project_id,
        region=default_region,
        disk_resource={
            "name": data_disk_name,
            "replica_zones": [
                f"https://www.googleapis.com/compute/v1/projects/diregapic-samples/zones/{default_region}-b",
                f"https://www.googleapis.com/compute/v1/projects/diregapic-samples/zones/{default_region}-a",
            ],
        },
    )

    while operation.status != compute_v1.Operation.Status.DONE:
        operation = region_operations_client.wait(
            operation=operation.name, region=default_region, project=default_project_id
        )

    create_instance(
        source_instance_name,
        [
            {
                "device_name": boot_disk_name,
                "initialize_params": {
                    "disk_name": boot_disk_name,
                    "source_image": "projects/debian-cloud/global/images/family/debian-10",
                    "disk_size_gb": 10,
                },
                "auto_delete": True,
                "boot": True,
                "type_": "PERSISTENT",
            },
            {
                "device_name": data_disk_name,
                "source": f"projects/{default_project_id}/regions/{default_region}/disks/{data_disk_name}",
                "auto_delete": True,
                "type_": "PERSISTENT",
            },
        ],
    )

    process = subprocess.Popen(
        [
            "python3",
            "migrate_script.py",
            "-s",
            source_instance_name,
            "-z",
            default_zone,
            "-m",
            mig_name,
            "--regional",
            "--image_for_boot_disk",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    (output, _) = process.communicate()
    process.wait()

    assert "Migration successfully finished." in str(output)

    created_mig = region_instance_group_managers_client.get(
        project=default_project_id,
        region=default_region,
        instance_group_manager=mig_name,
    )

    assert created_mig.target_size == 1

    operation = region_instance_group_managers_client.delete_unary(
        project=default_project_id,
        region=default_region,
        instance_group_manager=mig_name,
    )

    while operation.status != compute_v1.Operation.Status.DONE:
        operation = region_operations_client.wait(
            operation=operation.name, region=default_region, project=default_project_id
        )

    delete_instance(source_instance_name)
