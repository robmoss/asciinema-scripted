import dataclasses
import json
import numpy as np
import os
import pexpect
import re
import tempfile
import time
import tomli
import tomli_w

from .cast import AsciiCast, OutputEvent, MarkerEvent, CommentEvent


@dataclasses.dataclass
class Action:
    action_id: str = dataclasses.field(init=False)

    def __post_init__(self):
        self.action_id = self.__class__.__name__


@dataclasses.dataclass
class Input(Action):
    text: str
    pre_nl_delay: float
    post_nl_delay: float


@dataclasses.dataclass
class Marker(Action):
    label: str


@dataclasses.dataclass
class Comment(Action):
    comment: str


@dataclasses.dataclass
class Filter:
    filter_id: str = dataclasses.field(init=False)

    def __post_init__(self):
        self.filter_id = self.__class__.__name__

    def apply(self, header, events):
        raise NotImplementedError()


@dataclasses.dataclass
class RegexReplacementFilter(Filter):
    regex: str
    replacement: str

    def modify_event(self, event):
        if isinstance(event, OutputEvent):
            new_data = re.sub(self.regex, self.replacement, event.data)
            return dataclasses.replace(event, data=new_data)
        else:
            return event

    def apply(self, header, events):
        new_events = [self.modify_event(event) for event in events]
        return new_events


@dataclasses.dataclass
class StartMarkerFilter(Filter):
    start_label: str

    def apply(self, header, events):
        new_events = []
        started = False
        for event in events:
            if started:
                new_events.append(event)
            elif isinstance(event, MarkerEvent):
                if event.label == self.start_label:
                    started = True
        return new_events


@dataclasses.dataclass
class EndMarkerFilter(Filter):
    end_label: str

    def apply(self, header, events):
        new_events = []
        for event in events:
            if isinstance(event, MarkerEvent):
                if event.label == self.end_label:
                    break
            new_events.append(event)
        return new_events


@dataclasses.dataclass
class CommentFilter(Filter):
    def modify_event(self, event, num_cols, num_rows):
        if not isinstance(event, CommentEvent):
            return event
        if event.top:
            line_num = 1
        else:
            line_num = num_rows
        # NOTE: display comments with reversed foreground/background colours.
        rev_start = '\u001b[7m'
        rev_end = '\u001b[m'
        comment = f'{rev_start}{event.comment:^{num_cols}}{rev_end}'
        data = f'\u001b[s\u001b[{line_num};1H{comment}\u001b[u'
        return OutputEvent(event.time, data)

    def apply(self, header, events):
        w = header.width
        h = header.height
        new_events = [self.modify_event(event, w, h) for event in events]
        return new_events


def parse_filter(filter_tbl):
    f_class = filter_tbl['filter_id']
    kwargs = {k: v for k, v in filter_tbl.items() if k != 'filter_id'}
    if f_class == 'RegexReplacementFilter':
        return RegexReplacementFilter(**kwargs)
    elif f_class == 'StartMarkerFilter':
        return StartMarkerFilter(**kwargs)
    elif f_class == 'EndMarkerFilter':
        return EndMarkerFilter(**kwargs)
    elif f_class == 'CommentFilter':
        return CommentFilter(**kwargs)
    else:
        raise ValueError(f'Invalid filter {f_class}')


def parse_filters(filter_list):
    return tuple(parse_filter(filter_tbl) for filter_tbl in filter_list)


def parse_action(action_tbl):
    if isinstance(action_tbl, str):
        return action_tbl
    s_class = action_tbl['action_id']
    kwargs = {k: v for k, v in action_tbl.items() if k != 'action_id'}
    if s_class == 'Input':
        return Input(**kwargs)
    elif s_class == 'Marker':
        return Marker(**kwargs)
    elif s_class == 'Comment':
        return Comment(**kwargs)
    else:
        raise ValueError(f'Invalid step {s_class}')


def parse_actions(action_list):
    return tuple(parse_action(action_tbl) for action_tbl in action_list)


def send_line(proc, content, rng, typing_delay, pre_nl_delay, post_nl_delay):
    for char in content:
        proc.send(char)
        time.sleep(rng.uniform(**typing_delay))
    time.sleep(rng.uniform(**pre_nl_delay))
    proc.send('\n')
    final_delay = rng.uniform(**post_nl_delay)
    time.sleep(final_delay)
    return final_delay


@dataclasses.dataclass
class Script:
    output_file: str
    start_delay: float
    end_delay: float
    typing_delay: tuple[float, float]
    pre_nl_delay: tuple[float, float]
    post_nl_delay: tuple[float, float]
    with_comments: bool
    comments_at_top: bool
    actions: tuple[str | Input | Marker | Comment]
    filters: tuple[Filter]
    cols: int | None = None
    rows: int | None = None

    @classmethod
    def default(cls, output_file, **kwargs):
        defaults = {
            'output_file': output_file,
            'start_delay': 0.3,
            'end_delay': 0.5,
            'typing_delay': (0.05, 0.1),
            'pre_nl_delay': (0.2, 0.2),
            'post_nl_delay': (0.8, 1.0),
            'with_comments': False,
            'comments_at_top': False,
            'actions': tuple(),
            'filters': tuple(),
            'cols': None,
            'rows': None,
        }
        defaults.update(**kwargs)
        return cls(**defaults)

    def with_comments_enabled(self, at_top):
        # Ensure that the script has a CommentFilter to turn Comment actions
        # into OutputEvent instances.
        has_comment_filter = any(
            isinstance(f, CommentFilter) for f in self.filters
        )
        if has_comment_filter:
            filters = self.filters
        else:
            filters = self.filters + (CommentFilter(),)
        return dataclasses.replace(
            self, with_comments=True, comments_at_top=at_top, filters=filters
        )

    def with_actions(self, actions):
        return dataclasses.replace(self, actions=tuple(actions))

    def with_filters(self, filters):
        return dataclasses.replace(self, filters=tuple(filters))

    def run(self, quiet=False):
        rng = np.random.default_rng(seed=12345)
        typing_delay = dict(
            zip(['low', 'high'], self.typing_delay, strict=True)
        )
        pre_nl_delay = dict(
            zip(['low', 'high'], self.pre_nl_delay, strict=True)
        )
        post_nl_delay = dict(
            zip(['low', 'high'], self.post_nl_delay, strict=True)
        )

        rec_args = ['--overwrite']

        # Add columns and rows, if defined.
        if self.cols is not None:
            rec_args.extend(['--cols', str(self.cols)])
        if self.rows is not None:
            rec_args.extend(['--rows', str(self.rows)])

        # Run inside a GNU screen session in order to display comments.
        if self.with_comments:
            screen_rc = tempfile.NamedTemporaryFile('w', delete=False)
            if self.comments_at_top:
                action = 'first'
            else:
                action = 'last'
            screen_rc.write(f'hardstatus always{action}line\n')
            screen_rc.write('hardstatus string " "\n')
            screen_rc.write('altscreen on\n')
            screen_rc.close()
            rec_args.insert(0, '-c')
            rec_args.insert(1, f'screen -c "{screen_rc.name}"')

        cmd_args = ['rec'] + rec_args + [self.output_file]
        proc = pexpect.spawn('asciinema', cmd_args)
        t0 = time.time()
        newline_delay = 0

        time.sleep(self.start_delay)

        insert_events = []

        for action in self.actions:
            if isinstance(action, str):
                content = action
                posargs = [typing_delay, pre_nl_delay, post_nl_delay]
            elif isinstance(action, Input):
                content = action.text
                posargs = [
                    typing_delay,
                    {'low': action.pre_nl_delay, 'high': action.pre_nl_delay},
                    {
                        'low': action.post_nl_delay,
                        'high': action.post_nl_delay,
                    },
                ]
            elif isinstance(action, Marker):
                rel_time = time.time() - t0
                # NOTE: make the marker appear *before* the next line begins.
                rel_time -= 0.8 * newline_delay
                rel_time = round(rel_time, 3)
                insert_events.append(MarkerEvent(rel_time, action.label))
                continue
            elif isinstance(action, Comment):
                rel_time = time.time() - t0
                # NOTE: make the comment appear *before* the next line begins.
                rel_time -= 0.8 * newline_delay
                rel_time = round(rel_time, 3)
                insert_events.append(
                    CommentEvent(
                        rel_time, self.comments_at_top, action.comment
                    )
                )
                continue
            else:
                raise ValueError(f'Invalid input line {action}')

            newline_delay = send_line(proc, content, rng, *posargs)
            if not quiet:
                print('.', end='', flush=True)

        time.sleep(self.end_delay)

        proc.close()
        print()

        if self.with_comments:
            os.unlink(screen_rc.name)

        # Post-processing.
        cast = AsciiCast.load(self.output_file)
        cast = cast.insert_events(insert_events)
        cast = cast.filter_events(self.filters)
        cast.save(self.output_file)

    @classmethod
    def from_toml(cls, toml_file):
        with open(toml_file, 'rb') as f:
            data = tomli.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_json(cls, json_file):
        with open(json_file) as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_yaml(cls, yaml_file):
        try:
            import yaml
        except ModuleNotFoundError as e:
            msg = 'Could not import yaml module, is pyyaml installed?'
            raise ValueError(msg) from e

        with open(yaml_file) as f:
            data = yaml.load(f, Loader=yaml.Loader)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data):
        script_data = {key: value for key, value in data.items()}
        # Convert delay ranges from lists to tuples.
        script_data['typing_delay'] = tuple(script_data['typing_delay'])
        script_data['pre_nl_delay'] = tuple(script_data['pre_nl_delay'])
        script_data['post_nl_delay'] = tuple(script_data['post_nl_delay'])
        # Convert event and filter dictionaries to class instances.
        script_data['actions'] = parse_actions(script_data['actions'])
        script_data['filters'] = parse_filters(script_data['filters'])
        return cls(**script_data)

    def to_dict(self):
        data = dataclasses.asdict(self)
        tuple_fields = [
            key for key, value in data.items() if isinstance(value, tuple)
        ]
        for k in tuple_fields:
            data[k] = list(data[k])
        return data

    def to_toml(self, toml_file):
        data = self.to_dict()
        with open(toml_file, 'wb') as f:
            tomli_w.dump(data, f)

    def to_json(self, json_file):
        data = self.to_dict()
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=4)

    def to_yaml(self, yaml_file):
        try:
            import yaml
        except ModuleNotFoundError as e:
            msg = 'Could not import yaml module, is pyyaml installed?'
            raise ValueError(msg) from e

        data = self.to_dict()
        with open(yaml_file, 'w') as f:
            yaml.dump(data, f, sort_keys=False)
