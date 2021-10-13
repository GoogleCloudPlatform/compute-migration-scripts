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
    parser.add_argument("-s", "--source_instances", nargs="+", default=[])
    parser.add_argument("-b", "--base_instance_name")
    parser.add_argument("-z", "--source_instance_zone", required=True)
    parser.add_argument("-m", "--mig_name", required=True)

    parser.add_argument("--regional", dest="regional", action="store_true")
    parser.set_defaults(regional=False)

    args = parser.parse_args()

    if len(args.source_instances) == 0:
        parser.error(
            "You must provide at least one instance using --source_instances argument"
        )

    migrator = StatefulMIGMigrator(args)

    migrator.migrate()
