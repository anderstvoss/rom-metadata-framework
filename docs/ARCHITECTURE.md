# Architecture

## Overview

The framework separates ROM or disc-image identification from metadata
resolution.

The core flow is:

~~~text
input file
   |
   v
identification adapter
   |
   v
normalized identity
   |
   v
metadata resolver
   |
   v
resolved title metadata
~~~

## Identification adapters

Identification adapters perform platform- or format-specific inspection.

An adapter may produce fields such as:

~~~text
platform
format
hashes
serial
product_code
title_id
media_metadata
adapter
adapter_version
~~~

Different platforms may require different identification logic. The framework
must not assume that one hashing strategy or identifier type is sufficient for
every system.

Adapters may use:

- original project code;
- external upstream command-line tools;
- isolated helper programs;
- derived implementations where upstream licensing permits redistribution.

Third-party-derived implementations must remain behind a defined adapter
boundary and preserve required attribution and license information.

## Normalized identity

Identification results are converted into a common internal representation.

This normalized identity is the contract between identification adapters and
metadata resolvers.

Metadata resolvers must not depend on the implementation of the adapter that
produced the identity.

## Metadata resolvers

Metadata resolvers use normalized identity fields to locate human-readable
game and release information.

Potential resolver inputs include:

~~~text
SHA-1
MD5
CRC
serial
product code
title ID
platform
region
~~~

Resolvers may use local databases, downloadable datasets, or remote APIs.

Multiple resolvers may support the same platform.

## Licensing boundary

The core framework and each adapter are separate implementation boundaries for
provenance purposes.

Code copied, translated, adapted, or substantially derived from another
project must not be introduced until its license and redistribution
requirements have been reviewed.

Every populated third-party-derived adapter must record:

- upstream project;
- upstream repository;
- exact source revision where practical;
- upstream license;
- files or functions used;
- modifications made locally;
- required attribution.

Where direct code reuse would create incompatible licensing requirements for
the core framework, prefer an external process boundary rather than direct
linking or source incorporation.

## Test data

Public tests must use:

- synthetic fixtures;
- original fixtures created for this project; or
- freely redistributable test data with documented provenance.

Commercial ROMs, disc images, extracted copyrighted game binaries, and private
library contents must not be committed.
