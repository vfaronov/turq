Developing Turq
===============

Development environment
~~~~~~~~~~~~~~~~~~~~~~~

Set up::

  $ virtualenv /path/to/env
  $ source /path/to/env/bin/activate
  $ pip install -e .
  $ pip install -r tools/requirements.txt
  $ pip install ...    # any extra tools you like to have

Run tests::

  $ pytest

The delivery pipeline (Travis) enforces some other checks; if you want to run
them locally before pushing to GitHub, see ``.travis.yml``.

Versions of development tools (pytest, Pylint...) are pinned down to make
builds/QA reproducible. From time to time, they are `manually upgraded
<Maintenance_>`_.


Releasing a new version
~~~~~~~~~~~~~~~~~~~~~~~

#. Make sure that you're on master, it's clean and synced with GitHub,
   and that Travis and AppVeyor are green.

#. If necessary, update the version number in ``turq/__metadata__.py``
   (e.g. 0.12.0.dev4 → 0.12.0).

#. If releasing a "stable" (not pre-release) version, update ``CHANGELOG.rst``
   (usually just replace "Unreleased" with "<version> - <release date>",
   e.g. "0.12.0 - 2017-08-14").

#. Commit as necessary, for example::

     $ git commit -am 'Version 0.12.0'

#. Apply a Git tag for the version, for example::

     $ git tag -a v0.12.0 -m v0.12.0

#. Push master and tags::

     $ git push --tags origin master

#. Watch as Travis builds and uploads stuff to PyPI.

#. If releasing a "stable" (not pre-release) version, check that the
   `stable docs <http://turq.readthedocs.io/en/stable/>`_ have been updated
   (you may need to force-refresh the page to see it).

#. Bump the version number in ``turq/__metadata__.py``
   (e.g. 0.12.0 → 0.13.0.dev1).

#. Commit and push::

     $ git commit -am 'Bump version to 0.13.0.dev1'
     $ git push


Maintenance
~~~~~~~~~~~

- Watch for new versions of Python and dependencies (``install_requires``),
  and make sure Turq is compatible with them.

- Update development dependencies:

  #. Review ``tools/requirements.in`` and update if necessary.

  #. Pin down new versions::

       $ rm tools/requirements.txt
       $ pip-compile tools/requirements.in
       $ pip install -r tools/requirements.txt

- Look at recent Travis and AppVeyor build logs and make sure everything there
  looks alright.

- Check that the Python version trove classifiers in ``setup.py``
  are up-to-date.

