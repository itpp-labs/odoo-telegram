=============
 User manual
=============


Preparation
===========

1. Install *requests* and *requests[security]* python libs::

    pip2 install -U requests
    pip2 install 'requests[security]'

2. Put token in settings:

* Open base.
* Go to ``Technical \ Parameters \ System Parameters``.
* Enter value for ``telegram.token``.

3. Turn off db filter in odoo configuration file.

4. Run odoo with these console keys:  **--workers=2 --load telegram,web**.