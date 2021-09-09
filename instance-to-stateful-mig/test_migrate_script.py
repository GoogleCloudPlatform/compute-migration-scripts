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

default_project_id = google.auth.default()[1]
default_zone = "us-central1-a"
default_region = "us-central1"
default_mig_name = "mig_name"
default_instance_name = "test-mig-instance"


def create_instance(instance_name: str) -> None:
    intance_create_request = compute_v1.InsertInstanceRequest(
        zone=default_zone,
        project=default_project_id,
        instance_resource={
            "name": instance_name,
            "disks": [
                {
                    "device_name": "mig-boot-disk",
                    "initialize_params": {
                        "source_image": "projects/debian-cloud/global/images/family/debian-10",
                        "disk_size_gb": 10,
                    },
                    "auto_delete": True,
                    "boot": True,
                    "type_": compute_v1.AttachedDisk.Type.PERSISTENT,
                }
            ],
            "machine_type": f"zones/{default_zone}/machineTypes/n1-standard-1",
            "network_interfaces": [{"name": "global/networks/default"}],
        },
    )

    operation = instance_client.insert(request=intance_create_request)
    while operation.status != compute_v1.Operation.Status.DONE:
        operation = operation_client.wait(
            operation=operation.name, zone=default_zone, project=default_project_id
        )


def delete_instance(instance_name: str) -> None:
    operation = instance_client.delete(
        project=default_project_id, zone=default_zone, instance=instance_name
    )

    while operation.status != compute_v1.Operation.Status.DONE:
        operation = operation_client.wait(
            operation=operation.name, zone=default_zone, project=default_project_id
        )


def test_without_source_instance_name(capsys: typing.Any) -> None:
    process = subprocess.Popen(
        ["python3", "migrate_script.py", "-z", default_zone, "-m", default_mig_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    (_, err) = process.communicate()

    assert (
        "error: the following arguments are required: -i/--source_instance_name"
        in str(err)
    )


def test_without_source_zone_name(capsys: typing.Any) -> None:
    process = subprocess.Popen(
        [
            "python3",
            "migrate_script.py",
            "-i",
            default_instance_name,
            "-m",
            default_mig_name,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    (_, err) = process.communicate()

    assert "error: the following arguments are required: -z/--source_zone" in str(err)


def test_without_mig_name(capsys: typing.Any) -> None:
    process = subprocess.Popen(
        [
            "python3",
            "migrate_script.py",
            "-i",
            default_instance_name,
            "-z",
            default_zone,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    (_, err) = process.communicate()
    process.wait()

    assert "error: the following arguments are required: -m/--mig_name" in str(err)


def test_without_target_name(capsys: typing.Any) -> None:
    process = subprocess.Popen(
        [
            "python3",
            "migrate_script.py",
            "-i",
            default_instance_name,
            "-z",
            default_zone,
            "-m",
            default_mig_name,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    (_, err) = process.communicate()
    process.wait()

    assert (
        "error: One of the following parameters: target_instance_name or delete_source_instance have to be set"
        in str(err)
    )


def test_equal_source_and_target(capsys: typing.Any) -> None:
    process = subprocess.Popen(
        [
            "python3",
            "migrate_script.py",
            "-i",
            default_instance_name,
            "-z",
            default_zone,
            "-m",
            default_mig_name,
            "-t",
            default_instance_name,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    (_, err) = process.communicate()
    process.wait()

    assert (
        "error: Parameters source_instance_name and target_instance_name have to be different. If you want to migrate instance and save the name, then set delete_source_instance parameter to True"
        in str(err)
    )


def test_zonal_migration(capsys: typing.Any) -> None:
    source_instance_name = default_instance_name + "-" + uuid.uuid4().hex[:10]
    target_instance_name = "target-" + default_instance_name + uuid.uuid4().hex[:10]
    mig_name = "mig-" + uuid.uuid4().hex[:10]

    create_instance(source_instance_name)

    process = subprocess.Popen(
        [
            "python3",
            "migrate_script.py",
            "-i",
            source_instance_name,
            "-z",
            default_zone,
            "-m",
            mig_name,
            "-t",
            target_instance_name,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    (output, _) = process.communicate()
    process.wait()

    assert "Migration successfully finished." in str(output)

    created_mig = instance_group_managers_client.get(
        project=default_project_id, zone=default_zone, instance_group_manager=mig_name
    )

    assert created_mig.target_size == 1

    operation = instance_group_managers_client.delete(
        project=default_project_id, zone=default_zone, instance_group_manager=mig_name
    )

    while operation.status != compute_v1.Operation.Status.DONE:
        operation = operation_client.wait(
            operation=operation.name, zone=default_zone, project=default_project_id
        )

    delete_instance(source_instance_name)


def test_regional_migration(capsys: typing.Any) -> None:
    source_instance_name = default_instance_name + "-" + uuid.uuid4().hex[:10]
    target_instance_name = "target-" + default_instance_name + uuid.uuid4().hex[:10]
    mig_name = "mig-" + uuid.uuid4().hex[:10]

    create_instance(source_instance_name)

    process = subprocess.Popen(
        [
            "python3",
            "migrate_script.py",
            "-i",
            source_instance_name,
            "-z",
            default_zone,
            "-m",
            mig_name,
            "-t",
            target_instance_name,
            "--regional",
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

    operation = region_instance_group_managers_client.delete(
        project=default_project_id,
        region=default_region,
        instance_group_manager=mig_name,
    )

    while operation.status != compute_v1.Operation.Status.DONE:
        operation = region_operations_client.wait(
            operation=operation.name, region=default_region, project=default_project_id
        )

    delete_instance(source_instance_name)


def test_delete_instance_after_migration(capsys: typing.Any) -> None:
    source_instance_name = default_instance_name + "-" + uuid.uuid4().hex[:10]
    mig_name = "mig-" + uuid.uuid4().hex[:10]

    create_instance(source_instance_name)

    process = subprocess.Popen(
        [
            "python3",
            "migrate_script.py",
            "-i",
            source_instance_name,
            "-z",
            default_zone,
            "-m",
            mig_name,
            "--delete_source_instance",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    (output, _) = process.communicate()
    process.wait()

    assert "Migration successfully finished." in str(output)

    created_mig = instance_group_managers_client.get(
        project=default_project_id, zone=default_zone, instance_group_manager=mig_name
    )

    assert created_mig.target_size == 1

    list_instances = instance_client.list(project=default_project_id, zone=default_zone)

    assert source_instance_name not in list_instances

    operation = instance_group_managers_client.delete(
        project=default_project_id, zone=default_zone, instance_group_manager=mig_name
    )

    while operation.status != compute_v1.Operation.Status.DONE:
        operation = operation_client.wait(
            operation=operation.name, zone=default_zone, project=default_project_id
        )
