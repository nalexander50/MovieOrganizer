import os
import re
import shutil
import subprocess
from argparse import ArgumentParser

from operations import Operations

PREFERRED_VIDEO_EXTENSION = '.mkv'

VIDEO_EXTENSIONS = [
    '.avi', '.mkv', '.mov', '.mp4', '.webm', '.wmv'
]

def main():
    argument_parser = ArgumentParser()
    argument_parser.add_argument('folder_path', help='Path to pre-named folder containing the movie files')
    argument_parser.add_argument('-m', '--many', help='Indicates that the provided folder contains many folders that should be processed', action='store_true')
    argument_parser.add_argument('--whatIf', help='Display changes that would be made. Does not modify any files.', action='store_false')

    operations_group = argument_parser.add_mutually_exclusive_group()
    operations_group.add_argument('--transcode', help='Indicates that the video files should be transcoded to MKV', action='store_true')
    operations_group.add_argument('--remux', help='Indicates that the video files should be remuxed to MKV', action='store_true')

    arguments = argument_parser.parse_args()

    contains_many = arguments.many
    should_modify = arguments.whatIf
    folder_path = os.path.normpath(arguments.folder_path)
    transcode = arguments.transcode
    remux = arguments.remux

    assert transcode is True or remux is True, 'An operations must be specified'

    operation = Operations.TRANSCODE if transcode else Operations.REMUX

    requires_manual_intervention = dict()

    if contains_many:
        proc_count = 0
        listed_dir = sorted([f for f in os.listdir(folder_path) if not f.startswith('.')])
        for dir_entry in listed_dir:
            dir_entry_path = os.path.join(folder_path, dir_entry)
            if os.path.isdir(dir_entry_path):
                proc_count += 1
                print(f'[{proc_count} of {len(listed_dir)}] Processing {dir_entry_path}')
                processed, error = process_folder(dir_entry_path, operation, modify=should_modify)
                if not processed:
                    requires_manual_intervention[dir_entry_path] = error
                    print('\tRequires manual intervention:')
                    print(f'\t\t{error}\n')
        pass
    else:
        print(f'Processing {folder_path}')
        processed, error = process_folder(folder_path, operation, modify=should_modify)
        if not processed:
            requires_manual_intervention[folder_path] = error
            print('\tRequires manual intervention:')
            print(f'\t\t{error}\n')

    if len(requires_manual_intervention) > 0:
        print('\n')
        print(f'{len(requires_manual_intervention)} folders require manual intervention')
        for path, error in requires_manual_intervention.items():
            print(f'\t{path}')
            print(f'\t\t{error}')
    
    print('Done')

def process_folder(folder_path, operation, modify=False):
    try:
        assert check_proper_folder_name(folder_path), 'Improper folder name'

        possible_video_matches = find_proper_video(folder_path)
        
        assert len(possible_video_matches) == 1, 'Could not automatically isolate correct video'
        video_path = possible_video_matches[0]

        renamed_video_path, rename_message = rename_proper_video(folder_path, video_path, modify=modify)
        print(f'\t{rename_message}')

        converted_path, convert_message = convert_proper_video(folder_path, renamed_video_path, operation, modify=modify)
        print(f'\t{convert_message}')

        delete_messages = delete_excess_files(folder_path, converted_path, modify=modify)
        for message in delete_messages:
            print(f'\t{message}')

        print('\n')

        return (True, None)
    except AssertionError as ae:
        return (False, str(ae))


def check_proper_folder_name(folder_path):
    folder_name = os.path.basename(folder_path)
    is_proper = re.match(r'^.+ \(\d\d\d\d\)$', folder_name) != None
    return is_proper

def extract_year(folder_path):
    folder_name = os.path.basename(folder_path)
    year_str = re.search(r'\(\d\d\d\d\)', folder_name).group()
    year = int(year_str[1:-1])
    return year

def find_proper_video(folder_path):
    year = extract_year(folder_path)

    video_file_matches = []
    for dir_entry_name in os.listdir(folder_path):
        dir_entry_path = os.path.join(folder_path, dir_entry_name)
        if not os.path.isdir(dir_entry_path):
            name, extension = os.path.splitext(dir_entry_name)
            if extension in VIDEO_EXTENSIONS:
                if str(year) in name:
                    video_file_matches.append(dir_entry_path)

    return video_file_matches

def rename_proper_video(folder_path, video_path, modify=False):
    new_name, new_extension = os.path.splitext(os.path.basename(folder_path))
    current_name, current_extension = os.path.splitext(os.path.basename(video_path))
    new_video_path = os.path.join(folder_path, f'{new_name}{current_extension}')

    if modify:
        os.rename(video_path, new_video_path)
        return (new_video_path, f'[RENAMED] {current_name}{current_extension} to {new_name}{current_extension}')
    else:
        return (new_video_path, f'Rename {current_name}{current_extension} to {new_name}{current_extension}')

def convert_proper_video(folder_path, video_path, operation, modify=False):
    current_name, current_extension = os.path.splitext(os.path.basename(video_path))
    if current_extension == PREFERRED_VIDEO_EXTENSION:
        return (video_path, f'{video_path} already encoded as {PREFERRED_VIDEO_EXTENSION}')
    new_video_path = os.path.join(folder_path, f'{current_name}{PREFERRED_VIDEO_EXTENSION}')

    if operation == Operations.TRANSCODE:
        if modify:
            subprocess.run(args=['handbrake', '-i', video_path, '--preset', 'H.264 MKV 1080p30', '-o', new_video_path], check=True)
            return (new_video_path, f'[TRANSCODED] {current_name}{current_extension} to {current_name}{PREFERRED_VIDEO_EXTENSION}\n\n\n')
        else:
            return (new_video_path, f'Transcode {current_name}{current_extension} to {current_name}{PREFERRED_VIDEO_EXTENSION}')
    elif operation == Operations.REMUX:
        if modify:
            subprocess.run(args=['ffmpeg', '-i', video_path, '-c', 'copy', '-map', '0', new_video_path], check=True)
            return (new_video_path, f'[REMUXED] {current_name}{current_extension} to {current_name}{PREFERRED_VIDEO_EXTENSION}\n\n\n')
        else:
            return (new_video_path, f'Remux {current_name}{current_extension} to {current_name}{PREFERRED_VIDEO_EXTENSION}')

def delete_excess_files(folder_path, proper_video_path, modify=False):
    messages = []
    for dir_entry in os.listdir(folder_path):
        dir_entry_path = os.path.join(folder_path, dir_entry)
        if dir_entry_path != proper_video_path:
            current_name, current_extension = os.path.splitext(os.path.basename(dir_entry_path))
            if modify:
                if os.path.isdir(dir_entry_path):
                    shutil.rmtree(dir_entry_path)
                else:
                    os.remove(dir_entry_path)
                messages.append(f'[DELETED] {current_name}{current_extension}')
            else:
                messages.append(f'Delete {current_name}{current_extension}')
    return messages

if __name__ == '__main__':
    main()