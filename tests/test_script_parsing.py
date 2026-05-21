from asciinema_scripted import Script
from demo import demo_script
from pathlib import Path


def test_script_parsing_json_round_trip(tmp_path: Path) -> None:
    json_file = tmp_path / 'test_script_parsing_round_trip.json'
    input_script = demo_script()
    input_script.to_json(json_file)
    parsed_script = Script.from_json(json_file)
    assert parsed_script == input_script


def test_script_parsing_toml_round_trip(tmp_path: Path) -> None:
    toml_file = tmp_path / 'test_script_parsing_round_trip.toml'
    input_script = demo_script()
    input_script.to_toml(toml_file)
    parsed_script = Script.from_toml(toml_file)
    assert parsed_script == input_script


def test_script_parsing_yaml_round_trip(tmp_path: Path) -> None:
    yaml_file = tmp_path / 'test_script_parsing_round_trip.yaml'
    input_script = demo_script()
    input_script.to_yaml(yaml_file)
    parsed_script = Script.from_yaml(yaml_file)
    assert parsed_script == input_script
