Importing data into SQUAD
*************************

SQUAD provides a ``import`` command that will import data from a directory into
a specified project

Usage
=====

::
    ./manage.py import GROUP/PROJECT /path/to/directory/


Input format
============

The input directory must have the following structure::

    B/
      env1/
        JID/
          metadata.json
          metrics.json
          tests.json
          attachment1.pdf
          attachment2.png
        JID/
          metadata.json
          metrics.json
          tests.json
          attachment1.pdf
          attachment2.png
      env2/
      ...
    B/
      ...
    B/
      ...
    ...

That is:

* the top directory contains one subdirectory for each build
* each build directory has one subdirectory for each environment in which the
  build was tested
* each environment directory has one subdirectory for each test job that was
  executed in that environment
* each test job directory must have inside it a file called  ``metadata.json``
  which contains the test run metadata. ``metadata.json`` **must** be present.
* each test job directory should contain files ``metrics.json``, and
  ``tests.json``, which are in the same format as described in README.md. Both
  are optional.
* Any file other than the above is considered an attachment and imported as
  such.

Note that the directory names are used as the identifier for builds,
environments, and test jobs.
