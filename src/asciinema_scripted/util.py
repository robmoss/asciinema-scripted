from .script import MarkerEvent


def marker_md_list(events, data_video_id=None):
    if data_video_id is None:
        data_video_attr = ''
    else:
        data_video_attr = f' data-video="{data_video_id}"'

    lines = []
    for event in events:
        if isinstance(event, MarkerEvent):
            link = (
                f'<a{data_video_attr}'
                f' data-seek-to="{event.time}"'
                f' href="javascript:;">{event.label}</a>'
            )
            lines.append(link)
    return lines


def print_marker_md_list(cast, data_video_id):
    lines = marker_md_list(cast.events, data_video_id)
    for ix, line in enumerate(lines):
        print(f'{ix + 1}. {line}')
