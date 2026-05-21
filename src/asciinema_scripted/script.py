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

from pathlib import Path
from typing import Any, Self, override

from .cast import (
    AsciiCast,
    Header,
    Event,
    Filter,
    OutputEvent,
    MarkerEvent,
    CommentEvent,
)


@dataclasses.dataclass
class Action:
    action_id: str = dataclasses.field(init=False)

    def __post_init__(self) -> None:
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
class RegexReplacementFilter(Filter):
    regex: str
    replacement: str

    def modify_event(self, event: Event) -> Event:
        if isinstance(event, OutputEvent):
            new_data = re.sub(self.regex, self.replacement, event.data)
            return dataclasses.replace(event, data=new_data)
        else:
            return event

    @override
    def apply(self, header: Header, events: list[Event]) -> list[Event]:
        new_events = [self.modify_event(event) for event in events]
        return new_events


@dataclasses.dataclass
class StartMarkerFilter(Filter):
    start_label: str

    @override
    def apply(self, header: Header, events: list[Event]) -> list[Event]:
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

    @override
    def apply(self, header: Header, events: list[Event]) -> list[Event]:
        new_events: list[Event] = []
        for event in events:
            if isinstance(event, MarkerEvent):
                if event.label == self.end_label:
                    break
            new_events.append(event)
        return new_events


@dataclasses.dataclass
class CommentFilter(Filter):
    def modify_event(
        self, event: Event, num_cols: int, num_rows: int
    ) -> Event:
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

    @override
    def apply(self, header: Header, events: list[Event]) -> list[Event]:
        w = header.width
        h = header.height
        new_events = [self.modify_event(event, w, h) for event in events]
        return new_events


def parse_filter(filter_tbl: dict[str, Any]) -> Filter:
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


def parse_filters(filter_list: list[dict[str, Any]]) -> list[Filter]:
    return list(parse_filter(filter_tbl) for filter_tbl in filter_list)


def parse_action(action_tbl: str | dict[str, Any]) -> str | Action:
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


def parse_actions(
    action_list: list[str | dict[str, Any]],
) -> list[str | Action]:
    return list(parse_action(action_tbl) for action_tbl in action_list)


def send_line(
    proc: 'pexpect.spawn[str]',
    content: str,
    rng: np.random.Generator,
    typing_delay: tuple[float, float],
    pre_nl_delay: tuple[float, float],
    post_nl_delay: tuple[float, float],
) -> float:
    for char in content:
        proc.send(char)
        time.sleep(rng.uniform(low=typing_delay[0], high=typing_delay[1]))
    time.sleep(rng.uniform(low=pre_nl_delay[0], high=pre_nl_delay[1]))
    proc.send('\n')
    final_delay: float = rng.uniform(
        low=post_nl_delay[0], high=post_nl_delay[1]
    )
    time.sleep(final_delay)
    return final_delay


@dataclasses.dataclass
class Script:
    output_file: str
    start_delay: float = 0.3
    end_delay: float = 0.5
    typing_delay: tuple[float, float] = (0.05, 0.1)
    pre_nl_delay: tuple[float, float] = (0.2, 0.2)
    post_nl_delay: tuple[float, float] = (0.8, 1.0)
    with_comments: bool = False
    comments_at_top: bool = False
    actions: list[str | Action] = dataclasses.field(default_factory=list)
    filters: list[Filter] = dataclasses.field(default_factory=list)
    cols: int | None = None
    rows: int | None = None

    def with_comments_enabled(self, at_top: bool) -> Self:
        # Ensure that the script has a CommentFilter to turn Comment actions
        # into OutputEvent instances.
        has_comment_filter = any(
            isinstance(f, CommentFilter) for f in self.filters
        )
        if has_comment_filter:
            filters = self.filters
        else:
            filters = self.filters + [CommentFilter()]
        return dataclasses.replace(
            self, with_comments=True, comments_at_top=at_top, filters=filters
        )

    def with_actions(self, actions: list[str | Action]) -> Self:
        return dataclasses.replace(self, actions=actions)

    def with_filters(self, filters: list[Filter]) -> Self:
        return dataclasses.replace(self, filters=filters)

    def run(self, quiet: bool = False) -> None:
        rng = np.random.default_rng(seed=12345)

        rec_args = ['--overwrite']

        # Add columns and rows, if defined.
        if self.cols is not None:
            rec_args.extend(['--cols', str(self.cols)])
        if self.rows is not None:
            rec_args.extend(['--rows', str(self.rows)])

        # Run inside a GNU screen session in order to display comments.
        screen_rc = None
        if self.with_comments:
            screen_rc = tempfile.NamedTemporaryFile('w', delete=False)
            if self.comments_at_top:
                comment_locn = 'first'
            else:
                comment_locn = 'last'
            screen_rc.write(f'hardstatus always{comment_locn}line\n')
            screen_rc.write('hardstatus string " "\n')
            screen_rc.write('altscreen on\n')
            screen_rc.close()
            rec_args.insert(0, '-c')
            rec_args.insert(1, f'screen -c "{screen_rc.name}"')

        cmd_args = ['rec'] + rec_args + [self.output_file]
        proc: pexpect.spawn[str] = pexpect.spawn(
            'asciinema', cmd_args, encoding='utf-8'
        )
        t0 = time.time()
        newline_delay: float = 0.0

        time.sleep(self.start_delay)

        insert_events: list[Event] = []

        action: str | Action
        for action in self.actions:
            if isinstance(action, str):
                content = action
                posargs = [
                    self.typing_delay,
                    self.pre_nl_delay,
                    self.post_nl_delay,
                ]
            elif isinstance(action, Input):
                content = action.text
                posargs = [
                    self.typing_delay,
                    (action.pre_nl_delay, action.pre_nl_delay),
                    (action.post_nl_delay, action.post_nl_delay),
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

        if screen_rc is not None:
            os.unlink(screen_rc.name)

        # Post-processing.
        cast = AsciiCast.load(self.output_file)
        cast = cast.insert_events(insert_events)
        cast = cast.filter_events(self.filters)
        cast.save(self.output_file)

    @classmethod
    def from_toml(cls, toml_file: str | Path) -> Self:
        with open(toml_file, 'rb') as f:
            data = tomli.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_json(cls, json_file: str | Path) -> Self:
        with open(json_file) as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_yaml(cls, yaml_file: str | Path) -> Self:
        try:
            import yaml
        except ModuleNotFoundError as e:
            msg = 'Could not import yaml module, is pyyaml installed?'
            raise ValueError(msg) from e

        with open(yaml_file) as f:
            data = yaml.load(f, Loader=yaml.Loader)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        script_data = {key: value for key, value in data.items()}
        # Convert delay ranges from lists to tuples.
        script_data['typing_delay'] = tuple(script_data['typing_delay'])
        script_data['pre_nl_delay'] = tuple(script_data['pre_nl_delay'])
        script_data['post_nl_delay'] = tuple(script_data['post_nl_delay'])
        # Convert event and filter dictionaries to class instances.
        script_data['actions'] = parse_actions(script_data['actions'])
        script_data['filters'] = parse_filters(script_data['filters'])
        return cls(**script_data)

    def to_dict(self) -> dict[str, Any]:
        data = dataclasses.asdict(self)
        tuple_fields = [
            key for key, value in data.items() if isinstance(value, tuple)
        ]
        for k in tuple_fields:
            data[k] = list(data[k])
        return data

    def to_toml(self, toml_file: str | Path) -> None:
        data = self.to_dict()
        with open(toml_file, 'wb') as f:
            tomli_w.dump(data, f)

    def to_json(self, json_file: str | Path) -> None:
        data = self.to_dict()
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=4)

    def to_yaml(self, yaml_file: str | Path) -> None:
        try:
            import yaml
        except ModuleNotFoundError as e:
            msg = 'Could not import yaml module, is pyyaml installed?'
            raise ValueError(msg) from e

        data = self.to_dict()
        with open(yaml_file, 'w') as f:
            yaml.dump(data, f, sort_keys=False)
