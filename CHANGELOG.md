## [1.3.6](https://github.com/berkacunas/turbo-tosec/compare/v1.3.5...v1.3.6) (2025-11-30)


### Bug Fixes

* **importer:** restore missing package name in import statement ([bdd7a5d](https://github.com/berkacunas/turbo-tosec/commit/bdd7a5d9ef61e7c9065369754ec9bba3a77859bc))

## [1.3.5](https://github.com/berkacunas/turbo-tosec/compare/v1.3.4...v1.3.5) (2025-11-30)


### Performance Improvements

* **importer:** add dedicated thread for progress bar timer updates ([37ed9a6](https://github.com/berkacunas/turbo-tosec/commit/37ed9a65e94bbd11e1640d612b99598e6964ba78))

## [1.3.4](https://github.com/berkacunas/turbo-tosec/compare/v1.3.3...v1.3.4) (2025-11-30)


### Bug Fixes

* add module name to imports ([43fdb72](https://github.com/berkacunas/turbo-tosec/commit/43fdb7290b6d13bdacc38943e920d07a081ae3f9))
* **ci:** install package in release workflow and fix version import path ([c7a46cc](https://github.com/berkacunas/turbo-tosec/commit/c7a46cc3e192014aea7d5004e70371cdc11cfa36))
* **cli:** print version ([ba87ae9](https://github.com/berkacunas/turbo-tosec/commit/ba87ae92d25974d454509a1a5a89192fc766c25d))
* conflict module name import ([9a5057d](https://github.com/berkacunas/turbo-tosec/commit/9a5057dcd958ba1c41c0ba2d893251098cc611ff))
* update test imports to reflect package structure ([7bb6557](https://github.com/berkacunas/turbo-tosec/commit/7bb65574a91f055d60dd2d83035b70a399594edd))

## [1.3.3](https://github.com/berkacunas/turbo-tosec/compare/v1.3.2...v1.3.3) (2025-11-30)


### Bug Fixes

* **ci:** add missing @semantic-release/exec dependency ([77e0f2a](https://github.com/berkacunas/turbo-tosec/commit/77e0f2ae5d85666b75393e725856b54c016eceb2))
* fix README.tr.md filename ([634d92e](https://github.com/berkacunas/turbo-tosec/commit/634d92e9e9ddb749760d8570317704804fa73772))

## [1.3.2](https://github.com/berkacunas/turbo-tosec/compare/v1.3.1...v1.3.2) (2025-11-29)


### Bug Fixes

* flush print ([b12b80f](https://github.com/berkacunas/turbo-tosec/commit/b12b80f85a119bc8a0c089d738fe0c0f62de19f0))

## [1.3.1](https://github.com/berkacunas/turbo-tosec/compare/v1.3.0...v1.3.1) (2025-11-29)


### Bug Fixes

* **build:** force include uuid and xml modules in hiddenimports to prevent runtime crash ([f2c71de](https://github.com/berkacunas/turbo-tosec/commit/f2c71de6afed485d0f1d61ba2627d47aa559502a))

# [1.3.0](https://github.com/berkacunas/turbo-tosec/compare/v1.2.2...v1.3.0) (2025-11-29)


### Features

* **cli:** add --about command to explain safety philosophy and usage ([b0a1c4b](https://github.com/berkacunas/turbo-tosec/commit/b0a1c4bcf3319398c7f6699b92b7494f75e293ee))

## [1.2.2](https://github.com/berkacunas/turbo-tosec/compare/v1.2.1...v1.2.2) (2025-11-29)


### Bug Fixes

* replace git token for workflow conflict ([0295e53](https://github.com/berkacunas/turbo-tosec/commit/0295e53240f40b64ccd8deac094114021fffe09c))

## [1.2.1](https://github.com/berkacunas/turbo-tosec/compare/v1.2.0...v1.2.1) (2025-11-28)


### Bug Fixes

* **build:** add duckdb to hiddenimports to prevent runtime errors ([59cf211](https://github.com/berkacunas/turbo-tosec/commit/59cf211270d28d0ae32f0d8ca626dac7a33a559e))

# [1.2.0](https://github.com/berkacunas/turbo-tosec/compare/v1.1.0...v1.2.0) (2025-11-28)


### Features

* **ci:** add automated cross-platform build workflow for single-file binaries ([cc2c60c](https://github.com/berkacunas/turbo-tosec/commit/cc2c60c80f533dc7b60ea098728ca7318dc4dc50))

# [1.1.0](https://github.com/berkacunas/turbo-tosec/compare/v1.0.0...v1.1.0) (2025-11-28)


### Features

* **importer:** add worker-based multi-threading for faster DAT parsing ([dc13c77](https://github.com/berkacunas/turbo-tosec/commit/dc13c773f44343e06339455ec285fb8674b1d20b))

# 1.0.0 (2025-11-27)


### Features

* initial project setup and core importer script ([a8aa85f](https://github.com/berkacunas/turbo-tosec/commit/a8aa85f4a9a155e0c1b0d13ba9c20018072576c9))
