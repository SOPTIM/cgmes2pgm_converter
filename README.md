# CGMES2PGM-Converter

`cgmes2pgm_converter` provides a library to convert Common Grid Model Exchange Standard (CGMES) datasets to [PowerGridModel](https://github.com/PowerGridModel/power-grid-model) format.
It was designed to apply the PGM State Estimation on a CGMES dataset.
The CGMES dataset is fetched from a SPARQL endpoint and converted to a PGM dataset.
This converter works with CGMES 3.0 / CIM 100 datasets, as well as CGMES 2.4 / CIM 16 datasets.

Methods to substitute additional measurements are included as well to improve state estimation (e.g. passive nodes).
[cgmes2pgm_suite](https://github.com/SOPTIM/cgmes2pgm_suite) provides additional tools for working with CGMES and PGM.

## Getting Started

The package can be installed from PyPI using pip:

```bash
pip install cgmes2pgm_converter
```

### Set up the CGMES-Model

The CGMES-Model needs to be imported as a dataset into a triplestore providing a SPARQL endpoint (e.g. [Apache Jena Fuseki](https://jena.apache.org/)).

Currently, the CGMES model needs to be stored in the default graph of the dataset. This approach may be updated in future versions.

### Conversion

```python
from cgmes2pgm_converter import CgmesToPgmConverter, CgmesDataset

dataset = CgmesDataset(
    base_url="http://localhost:3030/dataset_name",
    cim_namespace="http://iec.ch/TC57/2013/CIM-schema-cim16#", # for CGMES 2.4
    # "http://iec.ch/TC57/CIM100#", # for CGMES 3.0
)

converter = CgmesToPgmConverter(datasource=dataset)
input_data, extra_info = converter.convert()
```

See [cgmes2pgm_suite](https://github.com/SOPTIM/cgmes2pgm_suite) for an complete example of how to use the converter.

## Supported CGMES Classes

The following list of CGMES classes is supported by the converter:

- All Branches (ACLineSegment, EquivalentBranch)
- Links (Switch, Breaker, Disconnector)
- Transformers (2-Winding, 3-Winding)
  - RatioTapchanger
  - PhaseTapChangerTabular
  - PhaseTapChangerLinear, -Symmetrical, -Asymmetrical
- Measurements (P, Q, U, I\*)
- Generators & Loads
  - SynchronousMachine, AsynchronousMachine
  - ExternalNEtworkInjection
  - EnergyConsumer
  - StaticVarCompensator
- Shunts (Linear-, NonlinearShuntCompensator)
- DC Components
  - CsConverter, VsConverter
  - Replaced by loads since PGM does not support DC Components

\* Used to create Q-measurements

## License

This project is licensed under the [Apache License 2.0](LICENSE.txt).

## Dependencies

This project includes third-party dependencies, which are licensed under their own respective licenses.

- [cgmes2pgm_converter](https://pypi.org/project/cgmes2pgm_converter/) (Apache License 2.0)
- [bidict](https://pypi.org/project/bidict/) (Mozilla Public License 2.0)
- [numpy](https://pypi.org/project/numpy/) (BSD License)
- [pandas](https://pypi.org/project/pandas/) (BSD License)
- [power-grid-model](https://pypi.org/project/power-grid-model/) (Mozilla Public License 2.0)
- [power-grid-model-io](https://pypi.org/project/power-grid-model-io/) (Mozilla Public License 2.0)
- [SPARQLWrapper](https://pypi.org/project/SPARQLWrapper/) (W3C License)
- [XlsxWriter](https://pypi.org/project/XlsxWriter/) (BSD License)
- [PyYAML](https://pypi.org/project/PyYAML/) (MIT License)
- [StrEnum](https://pypi.org/project/StrEnum/) (MIT License)
- [SciPy](https://pypi.org/project/scipy/) (BSD License)

## Development

For local development, the package can be installed from source:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
pre-commit install
```

## Commercial Support and Services

For organizations requiring commercial support, professional maintenance, integration services,
or custom extensions for this project, these services are available from **SOPTIM AG**.

Please feel free to contact us via [powergridmodel@soptim.de](mailto:powergridmodel@soptim.de).

## Contributing

We welcome contributions to improve this project.
Please see our [Contributing Guide](CONTRIBUTING.md) for details on how to submit pull requests, report issues, and suggest improvements.

## Code of Conduct

This project adheres to a code of conduct adapted from the [Apache Foundation's Code of Conduct](https://www.apache.org/foundation/policies/conduct).
We expect all contributors and users to follow these guidelines to ensure a welcoming and inclusive community.
