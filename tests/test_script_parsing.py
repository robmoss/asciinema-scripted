from asciinema_scripted import (
    Script,
    Input,
    Marker,
    Comment,
    EndMarkerFilter,
    CommentFilter,
)


def test_script_parsing_json_round_trip(tmp_path):
    json_file = tmp_path / 'test_script_parsing_round_trip.json'
    input_script = demo_script()
    input_script.to_json(json_file)
    parsed_script = Script.from_json(json_file)
    assert parsed_script == input_script


def test_script_parsing_toml_round_trip(tmp_path):
    toml_file = tmp_path / 'test_script_parsing_round_trip.toml'
    input_script = demo_script()
    input_script.to_toml(toml_file)
    parsed_script = Script.from_toml(toml_file)
    assert parsed_script == input_script


def test_script_parsing_yaml_round_trip(tmp_path):
    yaml_file = tmp_path / 'test_script_parsing_round_trip.yaml'
    input_script = demo_script()
    input_script.to_yaml(yaml_file)
    parsed_script = Script.from_yaml(yaml_file)
    assert parsed_script == input_script


def demo_script():
    actions = [
        Comment('See what files are here'),
        'ls',
        Comment('How large are these files?'),
        Input(text='du -h *', pre_nl_delay=1, post_nl_delay=3),
        Marker(label='Sum disk usage of all files'),
        Comment('What is the total disk usage?'),
        Input(
            text='du -c -h * | grep total', pre_nl_delay=1, post_nl_delay=3
        ),
        Comment('Goodbye'),
        '# The end',
        Marker(label='END'),
        'exit',
    ]
    filters = [
        EndMarkerFilter(end_label='END'),
        CommentFilter(),
    ]
    script = (
        Script.default(
            output_file='demo_script.cast',
            cols=80,
            rows=24,
            typing_delay=(0.05, 0.25),
        )
        .with_actions(actions)
        .with_filters(filters)
        .with_comments_enabled(at_top=False)
    )
    return script
