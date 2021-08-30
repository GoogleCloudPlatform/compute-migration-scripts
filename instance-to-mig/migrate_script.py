import argparse

from mig_migrator import MIGMigrator

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-p", "--project")

    # source instance info
    parser.add_argument("-i", "--source_instance_name", required=True)
    parser.add_argument("-z", "--source_zone", required=True)

    parser.add_argument("-m", "--mig_name", required=True)

    # if target intance name wasn't set, you must set delete_source_instance to True
    parser.add_argument("-t", "--target_instance_name")
    parser.add_argument("--regional", dest="regional", action="store_true")
    parser.add_argument(
        "--delete_source_instance", dest="delete_source_instance", action="store_true"
    )

    parser.set_defaults(delete_source_instance=False)
    parser.set_defaults(regional=False)

    args = parser.parse_args()

    if args.target_instance_name is None and args.delete_source_instance is False:
        parser.error(
            "One of the following parameters: target_instance_name or delete_source_instance have to be set"
        )

    if (
        args.delete_source_instance is False
        and args.source_instance_name == args.target_instance_name
    ):
        parser.error(
            "Parameters source_instance_name and target_instance_name have to be different. If you want to migrate instance and save the name, then set delete_source_instance parameter to True"
        )

    migrator = MIGMigrator(args)

    migrator.migrate()
