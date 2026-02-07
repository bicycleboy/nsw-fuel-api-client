nsw-tas-fuel-api-client
============================================
[![](https://travis-ci.org/nickw444/nsw-fuel-api-client.svg?branch=master)](https://travis-ci.org/nickw444/nsw-fuel-api-client)
[![](https://coveralls.io/repos/nickw444/nsw-fuel-api-client/badge.svg)](https://coveralls.io/r/nickw444/nsw-fuel-api-client)
[![](https://img.shields.io/pypi/v/nsw-fuel-api-client.svg)](https://pypi.python.org/pypi/nsw-fuel-api-client/)

API Client for New South Wales (Australia) Government Fuel Check Service providing fuel prices for NSW and TAS.

## Why

Allows an application, such as [Home Assistant](https://www.home-assistant.io/), to integrate data from the [NSW Fuel Check API](https://api.nsw.gov.au/Product/Index/22). See also Home Assistant Integration https://github.com/bicycleboy/nsw_fuel_station.

## What

This repository contains multiple files, here is a overview:

File | Purpose | Documentation
-- | -- | --
`.github/ISSUE_TEMPLATE/*.yml` | Templates for the issue tracker | [Documentation](https://help.github.com/en/github/building-a-strong-community/configuring-issue-templates-for-your-repository)
`nsw_fuel/*.py` | Integration files, this is where everything happens. |
`demo.py` | A hack to demonstrate and explore the API |
`tests/test_*.py` | Unit and api integration tests. |
`LICENSE` | The license file for the project. | [Documentation](https://help.github.com/en/github/creating-cloning-and-archiving-repositories/licensing-a-repository)
`pyproject.toml` | Python setup and configuration for this integration. | [Documentation](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
`README.md` | The file you are reading now. | [Documentation](https://help.github.com/en/github/writing-on-github/basic-writing-and-formatting-syntax)



## Blame

This update is based on [nickw444/nsw-fuel-api-client ](https://github.com/nickw444/nsw-fuel-api-client) particularly dto.py (thanks Nick), it is not backwardly compatible and has not been reviewed by the original author.