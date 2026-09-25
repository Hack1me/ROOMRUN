# Translations

English (`en`) is the source language and the default application language.
Keep user-facing strings in English in Python and templates, and wrap them in
Django's translation helpers so other locales can translate them.

Extract server-rendered strings and JavaScript strings separately:

```bash
python manage.py makemessages --all --no-location
python manage.py makemessages --domain djangojs --all --no-location
python manage.py compilemessages
```

The `django` domain contains Python and template messages. The `djangojs`
domain contains strings requested from JavaScript with `gettext()`.

Supported languages are configured in the `LANGUAGES` setting in `config/settings/base.py`.
The extraction commands generate `django.po` (Portable Object) files under each
locale's `LC_MESSAGES` directory. Each translatable string is stored as a
`msgid` and its translation as a `msgstr`, for example:

```po
msgid "users"
msgstr "utilisateurs"
```

Compile the catalogues into `.mo` (Machine Object) files after updating
translations. The application uses these compiled files at runtime, so compile
them again whenever a `.po` file changes.

## Production

The production image runs `compilemessages` automatically at build time, so as long as your translated source files (PO) are up-to-date, you're good to go.

## Add a new language

1. Update the [`LANGUAGES` setting](https://docs.djangoproject.com/en/stable/ref/settings/#std-setting-LANGUAGES) to your project's base settings.
2. Create the locale folder for the language next to this file, e.g. `fr_FR` for French. Make sure the case is correct.
3. Run `makemessages` (as instructed above) to generate the PO files for the new language.
