from eplus_plotter.idf_outputs import parse_output_variables
from eplus_plotter.sample import VariableSpec

IDF = """
  Output:Variable,
    *,                         !- Key Value
    Zone Mean Air Temperature, !- Variable Name
    Timestep;                  !- Reporting Frequency

  Output:Variable,ZONE ONE,Zone Wetbulb Globe Temperature,Hourly;

  ! a stray comment
  Building,
    Simple One Zone,           !- Name
    0;                         !- North Axis

  output:variable, , Site Outdoor Air Drybulb Temperature, timestep;
"""


def test_parses_key_and_name():
    specs = parse_output_variables(IDF)
    assert VariableSpec("Zone Mean Air Temperature", "*") in specs
    assert VariableSpec("Zone Wetbulb Globe Temperature", "ZONE ONE") in specs


def test_empty_key_value_means_all():
    specs = parse_output_variables(IDF)
    # an omitted key value is EnergyPlus shorthand for "*"
    assert VariableSpec("Site Outdoor Air Drybulb Temperature", "*") in specs


def test_ignores_non_output_variable_objects():
    specs = parse_output_variables(IDF)
    assert len(specs) == 3
    assert all(s.name != "Simple One Zone" for s in specs)


def test_no_output_variables_returns_empty():
    assert parse_output_variables("Building, X, 0;") == []
