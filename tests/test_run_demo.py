from asciinema_scripted import AsciiCast
from asciinema_scripted.__main__ import main
from asciinema_scripted.util import marker_md_list
from pathlib import Path

from tests.test_script_parsing import demo_script


def test_run_demo():
    """
    Run the demonstration script and ensure that only 1 of the 2 markers is
    recorded (the other marker is used to truncate the recording).
    """
    expected_length = 1
    expected_marker = 'Sum disk usage of all files'

    # Load the script and ensure the output file does not exist.
    script = demo_script()
    output_file = Path(script.output_file)
    output_file.unlink(missing_ok=True)

    # Save the script to disk and run it.
    script_file = 'demo_script.yaml'
    script.to_yaml(script_file)
    main([script_file])

    # Ensure the output file exists.
    assert output_file.exists()

    # Ensure that the recording includes the expected marker.
    cast = AsciiCast.load(output_file)
    assert len(cast.events) > 1
    lines = marker_md_list(cast.events)
    assert len(lines) == expected_length
    assert expected_marker in lines[0]
