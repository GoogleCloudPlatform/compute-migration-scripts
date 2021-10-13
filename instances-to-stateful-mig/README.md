# Migrate group of single instances to stateful MIG

This page describes how to run a Python3 script to migrate your group of standalone
GCP instances to a stateful Managed Instance Group.

If you want to do the same manually, you can use this [tutorial](https://cloud.google.com/compute/docs/tutorials/migrate-workload-to-stateful-mig).

## Script steps
1. Create an instance template from the base instance (with all source
   properties except data disks)
2. Create an empty MIG
3. For each instance from source instances:
   1. If the instance hasn't been stopped, then stop it
   2. Clone all instance disks except the boot disk
   3. Create an instance in the MIG (with properties that match the base instance) and include the cloned disks from the source instance"
4. Print commands for cleaning up the source instances after you have verified that the stateful MIG serves your needs

## Assumptions
1. Script assumes all source instances have the same instance configuration
2. Script assumes stateless boot disk
3. Script will stop all the running standalone source instances
4. Script will not reuse standalone VM names
5. Script will leave the standalone VMs intact, for easy reverting if the MIG doesn't work out
   1. Script does not detach disks, so user incurs additional cost
   2. Script will create images from existing disks, which also incurs cost
6. Script does not support stateful IPs

## Requirements

To run this script you need to meet the following criteria:

* You need Python version >= 3.6.
* You need `pipenv` or other virtual environment manager to install the
  script dependencies.
* You need to enable the [Compute Engine API](https://cloud.google.com/compute/)
* **Important** Your instance will be stopped during the script execution

## Authentication

You should download a service account JSON keyfile and point to it using an
environment variable:

```
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/keyfile.json"
```

or use gcloud command:

```
gcloud auth application-default login
```

## Installation

* Clone the repository and move to the folder with the script

```
git clone https://github.com/GoogleCloudPlatform/compute-migration-scripts.git && cd compute-migrations/instance-to-stateful-mig
```

* Install virtual environment and dependencies

```
python3 -m venv env
source ./env/bin/activate
pip3 install -r requirements.txt
```

## Arguments and Usage
### Usage
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

### Arguments
### Quick reference table
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
show this help message and exit

### `-p`, `--project`
Name of the GCP instance you want to migrate. If project is not provided, it
will be taken from credentials.

### `-i`, `--source_instances`
List of your single GCP instances you want to migrate. You should provide at
least 1 instance.

### `-b`, `--base_instance_name`
Base GCP instance name. The template will be based on this instance. If skipped
then first instance from source_instances will be taken.

### `-z`, `--source_zone`
Zone name of the GCP instance you want to migrate.

### `-m`, `--mig_name`
Stateful MIG name, that will be created

### `--regional`
If this flag is set, then stateful MIG will be
[regional](https://cloud.google.com/compute/docs/instance-groups/regional-migs),
which deploys instances to multiple zones across the same region. If the flag
isn't set, then stateful MIG will be zonal, which deploys instances to a single
zone. Instance redistribution type will be equals to `NONE` by default, you can
change it manually after MIG creation.

## Execution example
```
python3 migrate_script.py -s instance-1 instance-2 instance-3 -z us-central1-a -m my-mig
Creating base instance template ...
Instance template instance-1-template-438c2e created
==========
Creating empty MIG my-mig...
MIG my-mig created
==========
Instance instance-1 is not stopped. Stopping ...
Instance instance-1 stopped
==========
Creating disk a-disk-1-2548e8 from disk a-disk-1
==========
Creating disk a-disk-2-37075e from disk a-disk-2
==========
Adding instance instance-1-ad545d to my-mig MIG
==========

Instance instance-2 is not stopped. Stopping ...
Instance instance-2 stopped
==========
Creating disk a-disk-3-30c7ed from disk a-disk-3
==========
Adding instance instance-2-f80a7d to my-mig MIG
==========

Instance instance-3 is not stopped. Stopping ...
Instance instance-3 stopped
==========
Adding instance instance-3-de19a0 to my-mig MIG
==========

Migration successfully finished. Time spent: 181 seconds.
If script finished successfully, you can use this command to delete source single instances:
* gcloud compute instances delete instance-1 instance-2 instance-3
To revert all changes, please use this clean up commands:
* gcloud compute instance-templates delete instance-1-template-438c2e
* gcloud compute instance-groups managed delete my-mig
* gcloud compute disks delete a-disk-1-2548e8
* gcloud compute disks delete a-disk-2-37075e
* gcloud compute disks delete a-disk-3-30c7ed
Futher steps:
- Configuring autohealing: https://cloud.google.com/compute/docs/tutorials/migrate-workload-to-stateful-mig#configuring_autohealing
- Using a stateful policy instead of per-instance configurations:
  https://cloud.google.com/compute/docs/tutorials/migrate-workload-to-stateful-mig#using_a_stateful_policy_instead_of_per-instance_configurations
- Adding more VMs:
  https://cloud.google.com/compute/docs/tutorials/migrate-workload-to-stateful-mig#adding_more_vms
```