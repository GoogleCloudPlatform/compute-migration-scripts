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

from stateful_mig_migrator import StatefulMIGMigrator

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-p", "--project")
    parser.add_argument("-i", "--source_instance_name", required=True)
    parser.add_argument("-z", "--source_zone", required=True)
    parser.add_argument("-m", "--mig_name", required=True)
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

    migrator = StatefulMIGMigrator(args)

    migrator.migrate()
