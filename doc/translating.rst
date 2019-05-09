====================================
Translating the SQUAD user interface
====================================

Just run `./scripts/translate` with your language code as the only parameter.
For example, for Brazilian Portuguese::

    $ ./scripts/translate pt_BR
    squad/core/locale/pt_BR/LC_MESSAGES/django.po: 0 translated messages, 22 untranslated messages.
    squad/frontend/locale/pt_BR/LC_MESSAGES/django.po: 0 translated messages, 212 untranslated messages.

The script will output the names of the translation files that need to be
edited, together with the current translation statistics. Edit the `*.po`
files, commit, and send a pull request.

This procedure is valid both for creating new translations, and for updating
existing ones.
