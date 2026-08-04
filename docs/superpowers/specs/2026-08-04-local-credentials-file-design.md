# Local Credentials File Design

## Goal

Allow the options-research CLI and its local Codex scheduled task to obtain the
Alpha Vantage key from a persistent, machine-local file without storing,
printing, or committing the key.

## Design

The default credentials file is:

```text
~/.config/earnings-options-research/credentials.env
```

It uses one dotenv-style assignment:

```text
ALPHAVANTAGE_API_KEY=<local value>
```

The loader accepts blank lines and comments, reads only the named key, and does
not log file contents or the parsed value. The process environment takes
precedence over the file so a caller can deliberately override the configured
key. If neither source provides a key, Alpha Vantage remains unavailable and
the existing nonfatal fallback behavior is retained.

On POSIX systems, the loader rejects a credentials file that is readable by
group or others. The setup command creates the directory and file with
owner-only permissions. The repository never contains the file or its value.

## CLI And Automation

Add a setup command that creates the secure file location and prints its path
only. It must not accept, echo, or persist a key argument. The user writes the
key into that local file once. The weekly Codex automation runs locally and
uses the same loader, so it needs no embedded credential or prompt change.

## Verification

Tests cover missing files, comments and blank lines, environment precedence,
invalid permissions, and the setup command's owner-only file mode. Tests must
not include a real credential-like value. Documentation explains setup,
permission requirements, and the lack of key material in repository artifacts.
