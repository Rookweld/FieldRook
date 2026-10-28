# Reading Windows Error Codes

A short field guide for turning an unfamiliar code into a workable lead.
This note explains shapes and lookup habits. It is background reading,
not a diagnosis of any single machine.

## Hex and Decimal Forms

Many Windows codes appear in two shapes that mean the same value. A
leading `0x` marks hexadecimal, while a plain number is usually decimal.
Convert between the two before comparing notes from different tools, or
you may chase two labels for one value. Keep the original text as shown
so the lookup stays traceable.

When you see a long hex value starting with `0x8`, treat it as a
candidate HRESULT. Shorter values with four or five decimal digits are
often plain Win32 codes. Record which shape you started from and which
tool printed it.

## Facility and Severity Bits

An HRESULT packs three ideas: severity, facility, and code. Severity
tells whether the value reports success or failure. Facility hints at
the area that raised it, such as storage, network, or security. The
remaining bits carry the specific code. You do not need to decode bits
by hand every time, but knowing the layout helps you ask better
questions about where a failure came from.

If the facility points away from the part you are fixing, pause. The
visible program may only be passing along a failure raised deeper in
the stack. Follow the facility hint before changing settings.

## Lookup Workflow

Start with the exact string, including the `0x` prefix when present.
Check the built-in message text first, then compare with a second
source such as event detail or a service log. When two sources agree
on the same name, you have a stable label to carry forward.

Write down the code, the name you found, and the source of that name.
A later reader should be able to repeat the lookup without guessing.
Avoid acting on a paraphrase alone; keep the literal code attached to
every note and every handoff.

## Common Misreadings

A frequent mistake is reading only the last three digits. Truncation
merges unrelated failures into one bucket. Another is mixing signed
and unsigned decimal forms, which flip the sign and hide the match.

Treat names as hints, not verdicts. A name like access denied points
at a permission path, but it does not say which file, share, or key
was involved. Collect the surrounding evidence before choosing a fix.
