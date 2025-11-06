# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

<!-- insertion marker -->
## [v0.2.0](https://github.com/WDGPH/immunization-charts-python/releases/tag/v0.2.0) - 2025-11-06

<small>[Compare with v0.1.0](https://github.com/WDGPH/immunization-charts-python/compare/v0.1.0...v0.2.0)</small>

### Added

- Add pypandoc and git-changelog to dev dependencies ([0e04cda](https://github.com/WDGPH/immunization-charts-python/commit/0e04cdadb2fed81511add1ae89a0f484300d45e1) by Justin Angevaare).
- Add documentation to PDF validation approach ([b545430](https://github.com/WDGPH/immunization-charts-python/commit/b545430659a0df746a2f173eb9fc573f3e8cb8f1) by Justin Angevaare).
- Add "measurements" to validation. Measure contact area. ([099e099](https://github.com/WDGPH/immunization-charts-python/commit/099e099a035ea7935c9d1c7cfbdf356f4bc3ac0d) by Justin Angevaare).
- Add back page-numbering ([adb196c](https://github.com/WDGPH/immunization-charts-python/commit/adb196cdc3decbd81fc6cd64550d0140b6bef593) by Justin Angevaare).
- Add warnings for duplicate client IDs ([0c9a881](https://github.com/WDGPH/immunization-charts-python/commit/0c9a8815a158655ca34227ddc1cb66b4d224fc9c) by Justin Angevaare).
- Added all materials for our email package that we send out to PHUs interested in our automation process. ([dddd08b](https://github.com/WDGPH/immunization-charts-python/commit/dddd08b4bb90f4dc85a2da1e45b00e424e6e05c6) by kassyray).
- Add `ty` typechecker (note pre-commit hook not yet available for tool) ([fe4faab](https://github.com/WDGPH/immunization-charts-python/commit/fe4faabd76e414e267d6ce7e9f721e72467133b6) by Justin Angevaare).
- Add code-coverage ([a32a0fe](https://github.com/WDGPH/immunization-charts-python/commit/a32a0feb75f6f716f000bf6c964a948ef359a586) by Justin Angevaare).
- Add optional QR data field to ClientArtifact dataclass ([523e4ab](https://github.com/WDGPH/immunization-charts-python/commit/523e4ab2fb10edde2e2f730ac754e184bc5d553c) by Justin Angevaare).
- Add gitGraph commands for PHU branch and feature checkout in BRANCHING.md ([d4512ad](https://github.com/WDGPH/immunization-charts-python/commit/d4512ade23e5981b018075773640ad0041042220) by kassyray).
- Added testing for generate_notices.sh, compile_notices.sh, and run_pipeline.sh, changed to using test_data dir instead of pytest fixture data ([aea9041](https://github.com/WDGPH/immunization-charts-python/commit/aea9041abdc2a1acbc1ed2911a1e3fa4cf48f9f8) by TiaTuinstra).
- Add example with multiple overdue disesases to example dataset ([57b4ef1](https://github.com/WDGPH/immunization-charts-python/commit/57b4ef157fe0db06fe7d15802b7fc21ccfb711fc) by Justin Angevaare).
- Add notice configuration support with customizable QR payload and contact details ([ef934f2](https://github.com/WDGPH/immunization-charts-python/commit/ef934f2b1fa270a8720eb8efe28d04dd1e267ab9) by Eswar Attuluri).
- Add notice configuration support with customizable contact details and QR payload templates ([bcc9006](https://github.com/WDGPH/immunization-charts-python/commit/bcc900657e6af5e13353687463a309818e0a82b6) by Eswar Attuluri).
- Add VIPER Branching Strategy document to outline branching practices ([bfacd20](https://github.com/WDGPH/immunization-charts-python/commit/bfacd200654135678cf30a82061ef883fc82be3c) by kassyray).
- Add  PDF encryption functionality ([b0e0cd2](https://github.com/WDGPH/immunization-charts-python/commit/b0e0cd26a3af4ae08cbb08b2ccaa5ad467f20948) by Eswar Attuluri).
- add initial pytest testing for preprocess.py, also runs with github actions on push/pull ([4a65546](https://github.com/WDGPH/immunization-charts-python/commit/4a6554630c437745665c2f739740cae5bdf4b19f) by TiaTuinstra).
- Add QR code generation feature to immunization notices ([5416bae](https://github.com/WDGPH/immunization-charts-python/commit/5416baeee73703c6c0b76b1adf2557227c92df86) by Eswar Attuluri).

### Fixed

- Fix tests for 10-digit client ID tests ([c1b31ca](https://github.com/WDGPH/immunization-charts-python/commit/c1b31ca605ba745f5d241dc6263da52971b0f314) by Justin Angevaare).

### Changed

- changed to using tmp_test_dir to store original input/output files ([909251e](https://github.com/WDGPH/immunization-charts-python/commit/909251ea58adf68abdd115385972af936b8aa844) by TiaTuinstra).
- changed cleanup to only delete generated files/folders; ask before overwriting existing files; preprocess.py takes in batch_size as parameter; changed test data file names to match school names ([979e955](https://github.com/WDGPH/immunization-charts-python/commit/979e955b5f2b7c3a344789dfc616e4dbc232f176) by TiaTuinstra).

### Removed

- Remove mention of OEN in docstring - not used for client id ([25a82ec](https://github.com/WDGPH/immunization-charts-python/commit/25a82ec41be4ed03961785b27b89b002c94ccb2d) by Justin Angevaare).
- Remove date delivered from qr code and pdf encryption template options ([34f98e8](https://github.com/WDGPH/immunization-charts-python/commit/34f98e86eed899b55e52069bcb72425e66a37d80) by Justin Angevaare).
- Remove shebang - not needed for `uv run` ([7238805](https://github.com/WDGPH/immunization-charts-python/commit/7238805b844a76913eb09885b5b420f660e26e59) by Justin Angevaare).
- Remove underscore prefixes from function names ([a22e428](https://github.com/WDGPH/immunization-charts-python/commit/a22e428de7d1e6be70e4089b5f035a45d8aaeb0e) by Justin Angevaare).
- Remove unused convenience function ([9a3fa7b](https://github.com/WDGPH/immunization-charts-python/commit/9a3fa7bce657297c2ac5d2d02514ed5b6af0fc60) by Justin Angevaare).
- Removed deprecated code in pdf encryption ([09656cb](https://github.com/WDGPH/immunization-charts-python/commit/09656cb7e868e6e382056fb7983bc675d502ab3c) by Justin Angevaare).
- Remove requirements.txt ([1e73f78](https://github.com/WDGPH/immunization-charts-python/commit/1e73f782736b85c465f6231bd85eaf865e618b6c) by Justin Angevaare).
- remove duplicated code ([3def256](https://github.com/WDGPH/immunization-charts-python/commit/3def256044a2a6b09115cf46ac23a6a03d64a6c0) by Eswar Attuluri).
- Remove French client info table and adjust English table for improved layout ([0c6dc5a](https://github.com/WDGPH/immunization-charts-python/commit/0c6dc5a92509fc7ce50ccf67dcd1a1ba0b92a69b) by Eswar Attuluri).
- Remove ipykernel from dev dependencies. Add pytest. ([6ec86f8](https://github.com/WDGPH/immunization-charts-python/commit/6ec86f8dd5e45886df110d417ca0d5daa769aaa7) by Justin Angevaare).
- Remove compiled Python bytecode file from the repository ([33a6b3a](https://github.com/WDGPH/immunization-charts-python/commit/33a6b3abd05020353280890d35c3125a76afca49) by Eswar Attuluri).

## [v0.1.0](https://github.com/WDGPH/immunization-charts-python/releases/tag/v0.1.0) - 2025-10-14

<small>[Compare with first commit](https://github.com/WDGPH/immunization-charts-python/compare/4d958d4f480786089baed1029f5b4f28ca3e3aee...v0.1.0)</small>

### Added

- Add no-cleanup flag to run_pipeline.sh and relate to tinymist use ([fe8c3a8](https://github.com/WDGPH/immunization-charts-python/commit/fe8c3a8ef6766d5749718c29c5994236f24a543f) by Justin Angevaare).
- Add doc contribution to branching table; correct environment setup with uv ([14fceb4](https://github.com/WDGPH/immunization-charts-python/commit/14fceb4599438ea6a8a251da7378d0de38e84f42) by Justin Angevaare).
- Add .gitignore to exclude output directory ([82dcf4a](https://github.com/WDGPH/immunization-charts-python/commit/82dcf4a0acf52fb8a34241e6c00e90ccf09a0fab) by kassyray).
- Add mock logo and signature for testing purposes. ([de5f83a](https://github.com/WDGPH/immunization-charts-python/commit/de5f83a4ffb0d6c8bc4d04ed47e61ccddff4feb3) by kassyray).
- Adding requirements.txt ([7cfc8b6](https://github.com/WDGPH/immunization-charts-python/commit/7cfc8b6ea1da7e409a2b8ad88d86b14af75bfd31) by kassyray).
- Add rodent dataset Excel file for analysis ([c4f533c](https://github.com/WDGPH/immunization-charts-python/commit/c4f533c7af61f5215872d96b8c413df0850c9b45) by kassyray).
- Add configuration files for disease mapping, parameters, vaccination references, and Excel output ([59b2bc5](https://github.com/WDGPH/immunization-charts-python/commit/59b2bc5c3913e6a4b987989134977e25719c8ee4) by kassyray).
- Add scripts for preprocessing, generating, compiling notices, and cleanup ([92d52d9](https://github.com/WDGPH/immunization-charts-python/commit/92d52d9cccda9976fdd69a3c2e61e9ee5db7a5f5) by kassyray).
- Adding files to run pipeline ([1114bd3](https://github.com/WDGPH/immunization-charts-python/commit/1114bd36989ffe0b3645904c2ee83c73ca33ac6f) by kassyray).

### Fixed

- Fix directory in searching for existing conf.typ ([d51f51c](https://github.com/WDGPH/immunization-charts-python/commit/d51f51c47adf7f86b44ce41b45b4eac07e9e1ec9) by Justin Angevaare).
- fix: update .gitignore strategy to ensure __pycache__ and .pyc files are not tracked ([b75862a](https://github.com/WDGPH/immunization-charts-python/commit/b75862a7175f93c7a41c85b93a2c63fcfb7b9687) by Justin Angevaare).
- Fix formatting and update contributor tagging in the contribution guide ([c27e7a8](https://github.com/WDGPH/immunization-charts-python/commit/c27e7a8273801b877d633e48310ea65f5ed6f925) by kassyray).

