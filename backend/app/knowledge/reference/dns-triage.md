# DNS Triage for Workstations

A short path for name resolution failures on a single computer. This
note explains the resolution chain and simple isolation habits. It is
background reading, not a diagnosis of any single machine.

## Resolution Chain

A lookup travels from the application to the local cache, then to the
configured resolvers, then outward to forwarders and authoritative
servers. Ask at each link whether the name was answered, missed, or
timed out. The first link that fails narrows the search a great deal.

Write down the exact hostname you tried and the exact error words.
A name that never existed fails differently from a name that stopped
answering. Keep the spelling, because one letter changes the path.

## Cache and Server Checks

Start with the local cache and the configured server list. A stale
cache entry can survive long after the server data was fixed. A
missing or unreachable server address explains timeouts better than
any distant outage theory.

Confirm which server answered by querying it directly when you can.
Compare the direct answer with the normal path. When they differ,
the middle layer deserves attention before the far end.

## Common Failure Patterns

NXDOMAIN means the name was not found in the data consulted. A
timeout means no answer arrived in time, which often points at
connectivity or a silent drop. SERVFAIL means a server tried and hit
an error along the way. These three words lead to different next
steps, so quote the exact one you saw.

Watch for split behaviour where short names fail but fully qualified
names work. That pattern points at suffix handling rather than at
the servers themselves. Note both results side by side.

## Isolation Steps

Change one thing at a time. Try the same hostname from a second
machine on the same network, then try a well-known public name from
the affected machine. The pair tells you whether the fault follows
the computer or follows the name.

Collect the resolver list, the cache state, and the timed result for
each attempt. A tidy table of what answered and what timed out is
worth more than a guess about the wider internet.
