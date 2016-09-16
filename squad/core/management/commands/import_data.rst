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
        JID/
          metadata.json
          metrics.json
          tests.json
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
  executed in that environment * each  test job directory can have inside it
  ``metadata.json``, ``metrics.json``, and ``tests.json``, which are in the
  same format as described in README.md.

Note that the directory names are used as the identifier for builds,
environments, and test jobs.
