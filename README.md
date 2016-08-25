# SQUAD - Software Quality Dashboard

## Data model

```
+----+  * +-------+  * +-----+  * +-------+  * +----+ *   1 +-----+
|Team|--->|Project|--->|Build|--->|TestRun|--->|Test|------>|Suite|
+----+    +-------+    +-----+    +-------+    +----+       +-----+
                                    | *   |                    ^ 1
                                    |     |  * +---------+ *   |
                                    |     +--->|Benchmark|-----+
                                    |          +---------+
                                    v 1
                                  +-----------+
                                  |Environment|
                                  +-----------+
```

SQUAD is multi-team and multi-project. Each team can have multiple projects.
For each project, you can have multiple builds, and for each build, multiple
test runs. Each test run can include multiple test results, which can be either
pass/fail results, or benchmark results, containing one or more measurement
values. Test and benchmark results can belong to a Suite, which is a basically
used to group and analyze results together. Every test suite must be associated
with exactly one Environment, which describes the environment in which the
tests were executed, such as hardware platform, hardware configuration, OS,
build settings (e.g. regular compilers vcs optimized compilers), etc. Results
are always organized by environments, so we can compare apples to apples.

## Submitting results

The API is the following

**POST** /api/:team/:project/:build/:environment

* `:team` is the team identifier. It must exist previously
* `:project` is the project identifier. It will be craeted a automatically if
  it does not exist previously.
* `:build` is the build identifier. It can be a git commit hash, a Android
  manifest hash, or anything really. Extra information on the build can be
  submitted as an attachment. If a build timestamp is not informed there, the
  time of submission is assumed.
* `:environment` is the environmenr identitifer. It will be created
  automatically if does not exist before.

The actual test data must be submitted as file attachments in the `POST`
request, with the following names:

* `buildinfo`: extra information on the build.
* `metadata`: arbitrary metadata about the execution environment.
* `tests`: test results data
* `benchmarks`: benchmark results data

See [Input file formats](#input-file-formats) below for details on the file
formats that are accepted.

Example:

```
$ curl \
    --header "Token: 4971b4afe1470316a6463a9eb1f39742" \
    --form buildinfo=@/path/to/buildinfo.json \
    --form metadata=@/path/to/metadata.json \
    --form tests=@/path/to/test-rsults.json \
    --form benchmarks=@/path/to/benchmark-results.json \
    https://squad.example.com/api/my-team/my-project/20160630/my-ci-env
```

Since test results should always come from automation systems, the API is the
only way to submit results into the system. Even manual testing should be
automated with a driver program that asks for user input, and them at the end
prepares all the data in a consistent way, and submits it to dashboard.

## Input file formats

### Test results

_TBD_

### Benchmark results

_TBD_

## How to support multiple use cases

* Branches: use separate projects, one per branch. e.g. `foo-master` and
  `foo-stable`.
* ...

## License

Copyright © 2016 Linaro Limited

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
