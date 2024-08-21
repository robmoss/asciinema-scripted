# Generate scripted asciinema recordings

[asciinema](https://docs.asciinema.org/) is "a suite of tools for recording, replaying, and sharing terminal sessions".

This repository provides an `asciinema-scripted` tool that allows you to record terminal sessions with the following features:

* Terminal input is predefined, so that you can avoid typing mistakes;

* Input speed can be controlled, so that viewers can easily follow the input;

* Input delays can be sampled at random, to mimic human typing;

* [Markers](https://docs.asciinema.org/manual/player/markers/) are defined relative to input events, so their times are calculated automatically;

* Comments can be displayed in a "subtitle" bar at the top or bottom of the terminal — a feature introduced by [asciinema-comment](https://github.com/hydrargyrum/asciinema-comment).

Note that there are many other [asciinema tools](https://docs.asciinema.org/integrations/), which you may find useful.

## License

The code is distributed under the terms of the [BSD 3-Clause license](https://opensource.org/licenses/BSD-3-Clause) (see `LICENSE`).

## Requirements

- [asciinema](https://docs.asciinema.org/) version 2.2.0 or newer.
- [GNU Screen](https://www.gnu.org/software/screen/) for displaying comments.

## Installation

Install `asciinema-scripted` from this repository:

```sh
git clone https://github.com/robmoss/asciinema-scripted.git
pip install -e asciinema-scripted
```

## Usage

Record terminal sessions whose inputs are defined in `script.yaml` by running:

```sh
asciinema-scripted script.yaml
```

## Writing scripts

See the provided [demo_script.yaml](https://github.com/robmoss/asciinema-scripted/blob/master/demo_script.yaml) for an example.

A script should define the following top-level values:

- `output_file`: The session recording file (typically ends in `.cast`);
- `cols`: The terminal width;
- `rows`: The terminal height;
- `start_delay`: The delay (in seconds) between the start of the recording and performing the first action;
- `end_delay`: The delay (in seconds) between performing the final action and the end of the recording;
- `typing_delay`: A two-element list that defines the minimum and maximum delay (in seconds) between each input character;
- `pre_nl_delay`: A two-element list that defines the minimum and maximum delay (in seconds) before ending a line of input with a newline;
- `post_nl_delay`:A two-element list that defines the minimum and maximum delay (in seconds) after ending a line of input with a newline;
- `with_comments`: Whether to record comments in a status bar;
- `comments_at_top`: Whether comments should be shown at the top or bottom of the terminal;
- `actions`: A list of script actions (see below);
- `filters`: A list of script filters (see below).

## Script actions

The `actions` list defines the sequence of scripted actions for the terminal session.

### Input

Enter lines of input as strings:

```yaml
actions:
- cd ~
- ls
```

You can override the default newline delays an individual line:

```yaml
actions:
- cd ~
- action_id: Input
  text: ls
  pre_nl_delay: 1
  post_nl_delay: 2
```

### Markers

Insert chapter markers with the `Marker` action:

```yaml
actions:
- cd ~
- action_id: Marker
  label: List the files in my home directory
- ls
```

### Comments

Insert comments with the `Comment` action:

```yaml
actions:
- cd ~
- action_id: Comment
  comment: List the files in my home directory
- ls
```

Scripts that use the `Comment` action must add `CommentFilter` to the list of filters (see below).

## Script filters

The `filters` list defines post-processing steps for the recorded terminal session.

### Start and end markers

The `StartMarkerFilter` and `EndMarkerFilter` filters can be used to record only a subset of the terminal session.
These filters search for a `Marker` action with a matching label.

For example, to ensure that a program is compiled, but only record running the program:

```yaml
actions:
- make
- action_id: Marker
  label: START
- ./run_program
- action_id: Marker
  label: END
- make clean
filters:
- filter_id: StartMarkerFilter
  start_label: START
- filter_id: EndMarkerFilter
  end_label: END
```

### Comments

To convert `Comment` actions into terminal output, use `CommentFilter`:

```yaml
actions:
- cd ~
- action_id: Comment
  comment: List the files in my home directory
- ls
filters:
- filter_id: CommentFilter
```

### Regular expression replacements

Perform regular expression replacements with `RegexReplacementFilter`.
For example, to change "Hello World" into "Goodbye World":

```yaml
actions:
- ls
filters:
- filter_id: RegexReplacementFilter
  regex: Hello World
  replacement: Goodbye World
```

This filter can be used to, e.g., hide parent directories in absolute paths:

```yaml
filters:
- filter_id: RegexReplacementFilter
  regex: /home/.*/my-project
  replacement: my-project
```
