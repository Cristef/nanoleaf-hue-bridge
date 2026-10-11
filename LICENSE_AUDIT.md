# License review

Review date: 2026-10-11.

## Project license and scope

The original bridge, installer, wizard, and tests are provided under
**PolyForm Noncommercial License 1.0.0**, with the required copyright notice in
[LICENSE](LICENSE). This permits the noncommercial purposes described in that
license, including private entertainment and hobby projects. It does not grant
commercial-use rights. The license also defines permitted uses for certain
noncommercial organizations; consult its text for the exact scope.

This is source-available software, not OSI-defined open source. Third-party
packages and their notices retain their own licenses. The project's
noncommercial restriction does not relicense or restrict those packages.

## Method and dependency inventory

The two versions pinned in requirements.txt were checked against their official
PyPI metadata and published wheel license files. Their runtime dependency tree
was resolved for CPython 3.11 on Linux x86_64, without installing or running the
downloaded packages. Every one of the 20 resolved wheels contained license
files. Original license and attribution files are preserved under
[licenses/third-party](licenses/third-party). Artifact SHA-256 hashes, versions,
metadata license declarations, and original file paths are recorded in
[licenses/dependency-manifest.json](licenses/dependency-manifest.json).

| Package | Audited version | Declared license |
| --- | --- | --- |
| [aiohappyeyeballs](https://pypi.org/project/aiohappyeyeballs/2.7.1/) | 2.7.1 | `PSF-2.0` |
| [aiohttp](https://pypi.org/project/aiohttp/3.14.5/) | 3.14.5 | `Apache-2.0 AND MIT` |
| [aiosignal](https://pypi.org/project/aiosignal/1.4.0/) | 1.4.0 | `Apache 2.0` |
| [attrs](https://pypi.org/project/attrs/26.1.0/) | 26.1.0 | `MIT` |
| [cffi](https://pypi.org/project/cffi/2.1.1/) | 2.1.1 | `MIT-0` |
| [chacha20poly1305-reuseable](https://pypi.org/project/chacha20poly1305-reuseable/0.13.2/) | 0.13.2 | `Apache-2.0 OR BSD-3-Clause` |
| [cryptography](https://pypi.org/project/cryptography/50.0.2/) | 50.0.2 | `Apache-2.0 OR BSD-3-Clause` |
| [frozenlist](https://pypi.org/project/frozenlist/1.8.0/) | 1.8.0 | `Apache-2.0` |
| [h11](https://pypi.org/project/h11/0.16.0/) | 0.16.0 | `MIT` |
| [HAP-python](https://pypi.org/project/HAP-python/5.0.0/) | 5.0.0 | `Apache-2.0` |
| [hue-entertainment](https://pypi.org/project/hue-entertainment/0.1.2/) | 0.1.2 | `Apache-2.0` |
| [idna](https://pypi.org/project/idna/3.20/) | 3.20 | `BSD-3-Clause` |
| [ifaddr](https://pypi.org/project/ifaddr/0.2.0/) | 0.2.0 | `MIT` |
| [multidict](https://pypi.org/project/multidict/7.1.0/) | 7.1.0 | `Apache-2.0` |
| [orjson](https://pypi.org/project/orjson/3.13.0/) | 3.13.0 | `MPL-2.0 AND (Apache-2.0 OR MIT)` |
| [propcache](https://pypi.org/project/propcache/0.5.4/) | 0.5.4 | `Apache-2.0` |
| [pycparser](https://pypi.org/project/pycparser/3.11/) | 3.11 | `BSD-3-Clause` |
| [typing_extensions](https://pypi.org/project/typing_extensions/4.16.0/) | 4.16.0 | `PSF-2.0` |
| [yarl](https://pypi.org/project/yarl/1.25.1/) | 1.25.1 | `Apache-2.0` |
| [zeroconf](https://pypi.org/project/zeroconf/0.151.5/) | 0.151.5 | `LGPL-2.1-or-later` |

The indirect dependencies are not pinned by this project. This inventory is a
review snapshot, not a lock file or a guarantee about future installations.
Other architectures, Python versions, source builds, and newly resolved versions
may have different artifacts and license notices. Optional QR-code and testing
extras were not requested by the installer and are outside this inventory.

## Findings and distribution requirements

- HAP-python 5.0.0 and hue-entertainment 0.1.2 are Apache-2.0. The former's
  original LICENSE also contains upstream attribution details, which are
  preserved alongside its AUTHORS file.
- zeroconf is LGPL-2.1-or-later. It remains a separate, unmodified Python package,
  installed by pip and replaceable in the virtual environment. Its license does
  not require unrelated bridge source files to use LGPL. Redistributing a ready
  container or binary bundle requires a separate LGPL compliance check,
  including applicable source availability and replacement/relinking rights.
- orjson declares MPL-2.0 AND (Apache-2.0 OR MIT). Preserve all relevant notices
  and provide the applicable covered source and source-availability information
  when redistributing its binaries. MPL obligations apply to covered files,
  rather than automatically to unrelated project files.
- Apache, MIT, BSD, and PSF notices must be preserved where their terms require
  it. Apache NOTICE files, including those shipped by propcache and yarl, are
  preserved here. Dual-license OR expressions offer a choice; AND expressions
  identify obligations that must be considered together.
- The GitHub repository ships project source and license notices, not dependency
  implementation code, wheels, a prebuilt virtual environment, or an OS image.
  The installer fetches third-party packages separately. Debian packages retain
  their licenses and package copyright files under /usr/share/doc; they are not
  covered by the project's license or this Python dependency inventory.
- A future bundled release must also review native embedded components such as
  OpenSSL, Rust dependencies, and libffi, plus OS packages. This snapshot is not
  a complete SBOM or approval for distributing a prebuilt container.

## Source provenance and boundaries

The public repository contains the bridge implementation developed in this
project, its configuration wrappers, installer, and tests. It uses third-party
packages through imports rather than including their implementations. The
recorded development history states that NanoVirtz and MAGRGB implementation
code was not copied; protocol references are acknowledged in [NOTICE.md](NOTICE.md).
Review of the tracked source did not identify vendored third-party code. This
is not an exhaustive originality or copyright-ownership determination.

Licensing applies only to rights the licensor can grant. It does not certify
HomeKit compatibility, grant trademark rights, or establish legal clearance for
all protocol interoperability uses. Device identifiers and compatibility metadata
must not be presented as manufacturer endorsement.

## Earlier MIT revisions

Earlier private development revisions used MIT. Before public release, the
owner authorized keeping a local backup and replacing the published branch
history with a noncommercial initial revision. This does not revoke rights
already granted to anyone who lawfully received an earlier MIT copy. Git history
rewriting also cannot guarantee erasure of cached or previously fetched objects.

## Primary references

- [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0)
- [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)
- [GNU LGPL 2.1](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html)
- [Mozilla MPL 2.0 FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/)
- [OSI Open Source Definition](https://opensource.org/osd)

This is a technical license review of the listed artifacts, not a legal opinion
or a guarantee of enforceability in every jurisdiction.
