import argparse
import pathlib
import sys

from .cast import AsciiCast
from .script import Script
from .util import print_marker_md_list


def main(args=None):
    p = parser()
    args = p.parse_args(args=args)

    script_file = pathlib.Path(args.script_file).resolve()
    if not script_file.exists():
        raise ValueError(f'Invalid script file: "{args[0]}"')

    load_fun = script_loader(script_file, args.format)
    script = load_fun(script_file)

    if not args.dont_run:
        script.run(quiet=args.quiet)

    if args.print_markers:
        # NOTE: resolve the output file location with respect to the script
        # directory.
        output_file = script_file.parent.joinpath(script.output_file)
        cast = AsciiCast.load(output_file)
        print_marker_md_list(cast, data_video_id=args.data_id)

    return 0


def script_loader(script_file, file_format=None):
    if file_format is not None:
        file_format = file_format.upper()
        if file_format == 'JSON':
            return Script.from_json
        elif file_format == 'TOML':
            return Script.from_toml
        elif file_format == 'YAML':
            return Script.from_yaml
        else:
            raise ValueError(f'Invalid file format "{file_format}"')
    else:
        suffix = script_file.suffix.lower()
        if suffix == '.json':
            return Script.from_json
        elif suffix == '.toml':
            return Script.from_toml
        elif suffix in ['.yaml', '.yml']:
            return Script.from_yaml
        else:
            raise ValueError(f'Unknown file extension: {script_file.suffix}')


def parser():
    p = argparse.ArgumentParser(
        description='Generate scripted asciinema recordings'
    )
    output_grp = p.add_argument_group('Output options')
    output_grp.add_argument(
        '-d', '--dont-run', action='store_true', help="Don't run the script"
    )
    output_grp.add_argument(
        '-q',
        '--quiet',
        action='store_true',
        help="Don't print script progress",
    )
    output_grp.add_argument(
        '-m',
        '--print-markers',
        action='store_true',
        help='Print markers as a Markdown list',
    )
    output_grp.add_argument(
        '--data-id', help='HTML element ID for video element'
    )
    format_grp = p.add_argument_group(
        'Script format', 'Define the script format if it cannot be detected'
    )
    format_opts = format_grp.add_mutually_exclusive_group()
    format_opts.add_argument(
        '--json',
        action='store_const',
        const='JSON',
        dest='format',
        help='The script is stored in JSON format',
    )
    format_opts.add_argument(
        '--toml',
        action='store_const',
        const='TOML',
        dest='format',
        help='The script is stored in TOML format',
    )
    format_opts.add_argument(
        '--yaml',
        action='store_const',
        const='YAML',
        dest='format',
        help='The script is stored in YAML format',
    )
    p.add_argument('script_file', help='The scripted session to record')
    return p


if __name__ == '__main__':
    sys.exit(main())
