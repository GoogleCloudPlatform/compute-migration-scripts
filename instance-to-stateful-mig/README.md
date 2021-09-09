# Migrate single instance to stateful MIG

This page describes how to run Python3 script to migrate your single GCP instance to a stateful Managed Instance Group.

If you want to do the same manually, you can use this [tutorial](https://cloud.google.com/compute/docs/tutorials/migrate-workload-to-stateful-mig).

# Script steps
1. Stop source instance if the instance hasn't been stopped
2. Create images for all disks
3. Create an instance template from the source instance
4. Create an empty MIG
5. Delete the source instance if needed
6. Add a newly created instance to MIG

# Requirements

To run this script you need to meet the following criteria:

* You need Python version >= 3.6.
* You need `pipenv` or some other virtual environment manager to install the script dependencies.
* You need to enable the [Compute Engine API](https://cloud.google.com/compute/)
* **Important** Your instance will be stopped during the script execution

# Authentication

You should download a service account JSON keyfile and point to it using an environment variable:

```
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/keyfile.json"
```

# Installation

* Clone the repository and move to the folder with the script

```
git clone https://github.com/GoogleCloudPlatform/compute-migratins.git && cd compute-migrations/instance-to-stateful-mig
```

* Install virtual environment and dependencies

```
python3 -m venv env
source ./env/bin/activate
pip3 install -r requirements.txt
```

# Arguments and Usage
## Usage
```
python3 migrate_script.py [-h] [-p PROJECT] -i SOURCE_INSTANCE_NAME -z SOURCE_ZONE -m MIG_NAME [-t TARGET_INSTANCE_NAME] [--regional]
                         [--delete_source_instance]
```

## Arguments
### Quick reference table
|Short|Long                       |Default                     |Description
|-----|---------------------------|----------------------------|----------------------------------------
|`-h` |`--help`                   |                            |show this help message and exit
|`-p` |`--project`                |                            |project ID or project number of the GCP project you want to use.
|`-i` |`--source_instance_name`   |                            |name of the GCP instance you want to migrate.
|`-z` |`--source_zone`            |                            |zone name of the GCP instance you want to migrate.
|`-m` |`--mig_name`               |                            |name of the stateful MIG you want to create.
|`-t` |`--target_instance_name`   |                            |name of the stateful MIG you want to create.
|     |`--regional`               | False                      |if provide, will create regional stateful MIG, which deploys instances to multiple zones across the same region
|     |`--delete_source_instance` | False                      |if provide, instance will be deleted after script execuption

### `-h`, `--help`
show this help message and exit

### `-p`, `--project`
Name of the GCP instance you want to migrate. If project is not provided, it will be taken from credentials.

### `-i`, `--source_instance_name`
Name of the GCP instance you want to migrate.

### `-z`, `--source_zone`
Zone name of the GCP instance you want to migrate.

### `-m`, `--mig_name`
Stateful MIG name, that will be created

### `-t`, `--target_instance_name`
Target instance name, that will be added to the stateful MIG.
**Note** If `--source_instance_name` equals to `--target_instance_name` or empty, then you should explicitly set `--delete_source_instance` paremeter to True.

### `--regional`
If this flag is set, then stateful MIG will be [regional](https://cloud.google.com/compute/docs/instance-groups/regional-migs), which deploys instances to multiple zones across the same region. If the flas isn't set, then stateful MIG will be zonal, which deploys instances to a single zone.

### `--delete_source_instance`
If this flag is set, then the source instance will be deleted. 
**Important**: please, delete an instance if you strongly want to save original instance name. You can delete source instance manually after script execution.

# Execution example
```
python migrate_script.py -i test-instance -z europe-central2-b -m new-mig --delete_source_instance

Instance test-instance is not stopped. Stopping ...
Instance test-instance stopped
==========
Creating image for disk persistent-disk-0 ...
Disk image persistent-disk-0-image-1a48f9 generated
==========
Creating instance template ...
Instance template test-instance-template-61508f created
==========
Creating empty MIG new-mig...
MIG new-mig created
==========
Deleting source instance test-instance
Instance test-instance deleted
==========
Adding instance test-instance to new-mig ...
Instance added ...
==========
Migration successfully finished. Time spent: 90 seconds.
```