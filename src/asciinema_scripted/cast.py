"""
Provide wrapper classes for the asciinema file format (version 2).
"""

import dataclasses
import json
import re


@dataclasses.dataclass
class Theme:
    fg: str
    bg: str
    palette: list[str]


@dataclasses.dataclass
class Header:
    version: int
    width: int
    height: int
    timestamp: int | None = None
    duration: float | None = None
    idle_time_limit: float | None = None
    command: str | None = None
    title: str | None = None
    env: dict[str, str] | None = None
    theme: Theme | None = None

    def as_data(self):
        return {
            name: value
            for (name, value) in dataclasses.asdict(self).items()
            if value is not None
        }


@dataclasses.dataclass
class Event:
    time: float

    def __post_init__(self):
        self.event_id = self.__class__.__name__

    def as_data(self):
        raise NotImplementedError()


@dataclasses.dataclass
class OutputEvent(Event):
    data: str

    def as_data(self):
        return [self.time, 'o', self.data]


@dataclasses.dataclass
class InputEvent(Event):
    data: str

    def as_data(self):
        return [self.time, 'i', self.data]


@dataclasses.dataclass
class MarkerEvent(Event):
    label: str

    def as_data(self):
        return [self.time, 'm', self.label]


@dataclasses.dataclass
class CommentEvent(Event):
    """
    An event that updates the text in the GNU screen status bar.

    This is not a valid asciinema event, and must be converted into a valid
    output event (e.g., by using :class:`CommentFilter`).
    """

    top: bool
    comment: str

    def as_data(self):
        raise ValueError('Comment events must be filtered')


@dataclasses.dataclass
class ResizeEvent(Event):
    columns: int
    rows: int

    def as_data(self):
        return [self.time, 'r', f'{self.columns}x{self.rows}']


@dataclasses.dataclass
class AsciiCast:
    """
    An asciinema screencast.
    """

    header: Header
    events: list[Event]

    def filter_events(self, filters):
        event_list = self.events
        for event_filter in filters:
            event_list = event_filter.apply(self.header, event_list)
        return dataclasses.replace(self, events=event_list)

    def insert_events(self, events):
        if len(events) == 0:
            return self
        if len(self.events) == 0:
            return dataclasses.replace(self, events=events)

        event_times = [event.time for event in events]
        if event_times != sorted(event_times):
            raise ValueError('Events must be sorted chronologically')

        new_events = []
        next_event, remaining_events = events[0], events[1:]
        for current_event in self.events:
            if next_event is None or current_event.time <= next_event.time:
                new_events.append(current_event)
                continue

            while next_event.time < current_event.time:
                new_events.append(next_event)
                if remaining_events:
                    next_event = remaining_events[0]
                    remaining_events = remaining_events[1:]
                else:
                    next_event = None
                    break

            new_events.append(current_event)

        if next_event is not None:
            new_events.append(next_event)
        for event in remaining_events:
            new_events.append(event)

        return dataclasses.replace(self, events=new_events)

    @staticmethod
    def load(cast_file):
        """
        Load an asciinema screencast from ``cast_file``.
        """
        with open(cast_file) as f:
            data = [json.loads(line) for line in f]
        return parse_cast(data)

    def to_lines(self):
        header_record = self.header.as_data()
        event_records = [event.as_data() for event in self.events]
        records = [header_record] + event_records
        return [json.dumps(record) for record in records]

    def save(self, cast_file):
        """
        Save this asciinema screencast to ``cast_file``.
        """
        # NOTE: when saving, each item (header / event) must be a single line.
        lines = self.to_lines()
        with open(cast_file, 'w') as f:
            for line in lines:
                f.write(f'{line}\n')


def parse_cast(data):
    if isinstance(data[0], dict):
        try:
            header = Header(**data[0])
        except TypeError as e:
            raise ValueError('Invalid header data') from e
        if header.version != 2:
            raise ValueError(
                f'Unsupported file format version {header.version}'
            )
    else:
        raise ValueError('Missing asciicast header')
    events = []
    resize_re = re.compile(r'^([0-9]+)x([0-9]+)$')
    for ix, line in enumerate(data[1:]):
        if not (isinstance(line, list) and len(line) == 3):
            raise ValueError(f'Invalid event on line {ix + 1}')
        time_str = line[0]
        event_code = line[1]
        data = line[2]
        try:
            time = float(time_str)
        except ValueError as e:
            raise ValueError(
                'Invalid event time {time_str} on line {ix + 1}'
            ) from e
        if event_code == 'o':
            event = OutputEvent(time, data)
        elif event_code == 'i':
            event = InputEvent(time, data)
        elif event_code == 'r':
            m = resize_re.match(data)
            if m is None:
                raise ValueError(
                    f'Invalid resize data {data} on line {ix + 1}'
                )
            cols = int(m.group(1))
            rows = int(m.group(2))
            event = ResizeEvent(time, columns=cols, rows=rows)
        elif event_code == 'm':
            event = MarkerEvent(time, data)
        else:
            raise ValueError(
                f'Invalid event code {event_code} on line {ix + 1}'
            )
        events.append(event)
    return AsciiCast(header=header, events=events)
