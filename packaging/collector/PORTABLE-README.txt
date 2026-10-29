FieldRook Collector (portable, v1.0.0) — read-only evidence collection.
No install, no admin, no network. Copy this whole folder anywhere (USB OK)
and run FieldRook-Collector.exe from a console.

COLLECT (shows the per-category consent screen; refuses without --yes):

  FieldRook-Collector.exe collect --out package.zip --yes --hint "LABEL"

  Options: --categories services,os,events,network,tasks,procs
           --service NAME  --note FILE  (repeatable)  --fixture  --timeout S

VALIDATE a package (structure + hashes + manifest schema):

  FieldRook-Collector.exe validate package.zip

HELP:

  FieldRook-Collector.exe --help

PRIVACY: secrets, emails, usernames and hostnames are redacted on THIS
computer before the package is written. The hostname is stored only as a
hash plus your label. Full command lines are never collected. The package
is a ZIP you hand to the technician; nothing is transmitted automatically.

CHECKS: SHA256SUMS.txt lists every file in this folder (verify with
`certutil -hashfile <file> SHA256` or `Get-FileHash`). BUILD-BOM.txt
records the build toolchain and artifact hashes. This build is NOT
code-signed (not authorized for M025); expect a SmartScreen prompt on
first run from a download.
