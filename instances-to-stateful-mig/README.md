# Migrate a group of individual instances to a stateful MIG

This page describes how to run a Python3 script that automates
the migration of your group of individual instances to a stateful MIG.

If you want to perform the same steps manually, follow this [tutorial](https://cloud.google.com/compute/docs/tutorials/migrate-workload-to-stateful-mig).

## Script steps
The automated script performs the following steps to migrate your instances:

1. Stop all instances
2. Create an instance template based on the properties of a chosen instance, except for attached data disks.
3. Create an empty MIG.
4. For each instance in the original group, perform the following steps:
   1. Clone all instance disks except the boot disk.
   2. Create an instance in the MIG based on the instance template from point 1, and include the cloned disks from the source instance.
5. Print commands for cleaning up the source instances after you have verified that the stateful MIG serves your needs.

Note that the script leaves all standalone VMs stopped with their disks intact, for easy reverting 
if the MIG doesn't work as expected.
This results in additional costs, for the following reasons:

1.  The script doesn't detatch or delete the original disks.
2.  The script creates images from existing disks.

## Limitations

*   All source instances must have the same instance configuration.
*   Boot disks must be stateless.
*   Preservation of IP addresses is not supported.
*   The script stops all the running standalone source instances.
*   The script doesn't reuse the standalone VM names in the MIG.

## Requirements

To run this script you need to meet the following requirements:

* Python version >= 3.6.
* `pipenv` or other virtual environment manager to install the
  script dependencies.
* [Compute Engine API](https://cloud.google.com/compute/) enabled.

## Authentication

To authenticate your requests, download a service account JSON keyfile and point to it using an
environment variable:

```
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/keyfile.json"
```

Alternatively, use the following `gcloud` command:

```
gcloud auth application-default login
```

## Installation

* Clone the repository and move to the folder with the script.

```
git clone https://github.com/GoogleCloudPlatform/compute-migration-scripts.git && cd compute-migration-scripts/instances-to-stateful-mig
```

* Install virtual environment and dependencies.

```
python3 -m venv env
source ./env/bin/activate
pip3 install -r requirements.txt
```

## Arguments and Usage
## Usage
```
python3 migrate_script.py [-h] [-p PROJECT] [-s SOURCE_INSTANCES [SOURCE_INSTANCES ...]] [-b BASE_INSTANCE_NAME] -z SOURCE_INSTANCE_ZONE -m MIG_NAME [--regional]

optional arguments:
  -h, --help            show this help message and exit
  -p PROJECT, --project PROJECT
  -s SOURCE_INSTANCES [SOURCE_INSTANCES ...], --source_instances SOURCE_INSTANCES [SOURCE_INSTANCES ...]
  -b BASE_INSTANCE_NAME, --base_instance_name BASE_INSTANCE_NAME
  -z SOURCE_INSTANCE_ZONE, --source_instance_zone SOURCE_INSTANCE_ZONE
  -m MIG_NAME, --mig_name MIG_NAME
  --regional
```

## Quick reference table
|Short|Long                       |Default                     |Description
|-----|---------------------------|----------------------------|----------------------------------------
|`-h` |`--help`                   |                            |show this help message and exit
|`-p` |`--project`                |                            |project ID or project number of the GCP project you want to use.
|`-s` |`--source_instances`       |                            |list of your single GCP instances you want to migrate.
|`-b` |`--base_instance_name`     | source_instances[0]        |base GCP instance name (the template will be based on this instance)
|`-z` |`--source_zone`            |                            |zone name of the GCP instance you want to migrate.
|`-m` |`--mig_name`               |                            |name of the stateful MIG you want to create.
|     |`--regional`               | False                      |if provided, will create regional stateful MIG, which deploys instances to multiple zones across the same region

### `-h`, `--help`
Show the help text and exit.

### `-p`, `--project`
Project name of the GCP instance you want to migrate. If project is not provided, it
will be taken from credentials.

### `-s`, `--source_instances`
List of the individual GCP instances you want to migrate. You should provide at
least 1 instance.

### `-b`, `--base_instance_name`
Base GCP instance name. The template will be based on this instance. If skipped
then the first instance from `source_instances` will be taken.

### `-z`, `--source_zone`
Zone name of the GCP instance you want to migrate.

### `-m`, `--mig_name`
Name of the stateful MIG you want to create.

### `--regional`
If this flag is set, then stateful MIG will be
[regional](https://cloud.google.com/compute/docs/instance-groups/regional-migs),
which deploys instances to multiple zones across the same region. If the flag
isn't set, then stateful MIG will be zonal, which deploys instances to a single
zone. Instance redistribution type will be set to `NONE`. You cannot change 
instance redistribution for stateful MIGs. See [Limitations](https://cloud.google.com/compute/docs/instance-groups/configuring-stateful-migs#limitations)

## Execution example
```
python3 migrate_script.py -s instance-1 instance-2 instance-3 -z us-central1-a -m my-mig
Creating base instance template ...
Instance template instance-1-template-bf7831 created
==========
Creating empty MIG my-mig...
MIG my-mig created
==========
Creating disk a-disk-1-784c10 from disk a-disk-1
==========
Creating disk a-disk-2-133570 from disk a-disk-2
==========
Adding instance instance-1-f9443a to my-mig MIG
==========

Creating disk a-disk-3-b53e04 from disk a-disk-3
==========
Adding instance instance-2-757095 to my-mig MIG
==========

Adding instance instance-3-c80f95 to my-mig MIG
==========

Migration successfully finished. Time spent: 127 seconds.
Use the following command to delete the individual source instances:
* gcloud compute instances delete instance-1 instance-2 instance-3

To revert all changes, use this clean up commands:
* gcloud compute instance-templates delete instance-1-template-bf7831
* gcloud compute instance-groups managed delete my-mig
* gcloud compute disks delete a-disk-1-784c10
* gcloud compute disks delete a-disk-2-133570
* gcloud compute disks delete a-disk-3-b53e04

Futher steps:
- Configuring autohealing: https://cloud.google.com/compute/docs/tutorials/migrate-workload-to-stateful-mig#configuring_autohealing
- Using a stateful policy instead of per-instance configurations:
  https://cloud.google.com/compute/docs/tutorials/migrate-workload-to-stateful-mig#using_a_stateful_policy_instead_of_per-instance_configurations
- Adding more VMs:
  https://cloud.google.com/compute/docs/tutorials/migrate-workload-to-stateful-mig#adding_more_vms
```
