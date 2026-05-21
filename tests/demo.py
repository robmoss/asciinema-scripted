from asciinema_scripted import (
    Script,
    Action,
    Input,
    Marker,
    Comment,
    Filter,
    EndMarkerFilter,
    CommentFilter,
)


def demo_script() -> Script:
    actions: list[str | Action] = [
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
    filters: list[Filter] = [
        EndMarkerFilter(end_label='END'),
        CommentFilter(),
    ]
    script = (
        Script(
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
