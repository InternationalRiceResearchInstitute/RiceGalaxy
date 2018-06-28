.. figure:: https://galaxyproject.org/images/galaxy-logos/galaxy_project_logo.jpg
   :alt: Galaxy Logo

The latest information about Galaxy is available via `https://galaxyproject.org/ <https://galaxyproject.org/>`__

.. image:: https://img.shields.io/badge/questions-galaxy%20biostar-blue.svg
    :target: https://biostar.usegalaxy.org
    :alt: Ask a question

.. image:: https://img.shields.io/badge/chat-irc.freenode.net%23galaxyproject-blue.svg
    :target: https://webchat.freenode.net/?channels=galaxyproject
    :alt: Chat on irc
    
.. image:: https://img.shields.io/badge/chat-gitter-blue.svg
    :target: https://gitter.im/galaxyproject/Lobby
    :alt: Chat on gitter

.. image:: https://img.shields.io/badge/release-documentation-blue.svg
    :target: https://docs.galaxyproject.org/en/master/
    :alt: Release Documentation

.. image:: https://travis-ci.org/galaxyproject/galaxy.svg?branch=dev
    :target: https://travis-ci.org/galaxyproject/galaxy
    :alt: Inspect the test results

Galaxy Quickstart
=================

Galaxy requires Python 2.7 To check your python version, run:

.. code:: console

    $ python -V
    Python 2.7.3

Start Galaxy:

.. code:: console

    $ sh run.sh

Once Galaxy completes startup, you should be able to view Galaxy in your
browser at:

http://localhost:8080

You may wish to make changes from the default configuration. This can be
done in the ``config/galaxy.ini`` file. Tools can be either installed
from the Tool Shed or added manually. For details please see the Galaxy
wiki:

https://galaxyproject.org/admin/tools/add-tool-from-toolshed-tutorial/

Not all dependencies are included for the tools provided in the sample
``tool_conf.xml``. A full list of external dependencies is available at:

https://wiki.galaxyproject.org/Admin/Tools/ToolDependencies

Issues and Galaxy Development
=============================

Please see `CONTRIBUTING.md <CONTRIBUTING.md>`_ .

Roadmap
=============================

Interested in the next steps for Galaxy? Take a look here: https://github.com/galaxyproject/galaxy/issues/1928
