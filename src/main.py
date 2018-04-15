import os
import re
import subprocess
from argparse import ArgumentParser

PREFERRED_VIDEO_EXTENSION = '.mkv'

VIDEO_EXTENSIONS = [
    '.avi', '.mkv', '.mov', '.mp4', '.webm', '.wmv'
]

def main():
    argument_parser = ArgumentParser()
    argument_parser.add_argument('folder_path', help='Path to pre-named folder containing the movie files')
    argument_parser.add_argument('-m', '--many', help='Indicates that the provided folder contains many folders that should be processed', action='store_true')
    argument_parser.add_argument('--whatIf', help='Display changes that would be made. Does not modify any files.', action='store_false')

    arguments = argument_parser.parse_args()

    contains_many = arguments.many
    should_modify = arguments.whatIf
    folder_path = os.path.normpath(arguments.folder_path)

    requires_manual_intervention = []

    if contains_many:
        for dir_entry in os.listdir(folder_path):
            dir_entry_path = os.path.join(folder_path, dir_entry)
            if os.path.isdir(dir_entry_path):
                if not process_folder(dir_entry_path, modify=should_modify):
                    requires_manual_intervention.append(dir_entry_path)
                    print('\tRequires manual intervention...\n')
        pass
    else:
        if not process_folder(folder_path, modify=should_modify):
            requires_manual_intervention.append(folder_path)
            print('\tRequires manual intervention...\n')

    if len(requires_manual_intervention) > 0:
        print('\n')
        print(f'{len(requires_manual_intervention)} folders require manual intervention')
        for path in requires_manual_intervention:
            print(f'\t{path}')
    
    print('Done')

def process_folder(folder_path, modify=False):
    try:
        print(f'Processing {folder_path}')

        assert check_proper_folder_name(folder_path)

        possible_video_matches = find_proper_video(folder_path)
        
        assert len(possible_video_matches) == 1
        video_path = possible_video_matches[0]

        renamed_video_path, rename_message = rename_proper_video(folder_path, video_path, modify=modify)
        print(f'\t{rename_message}')

        transcoded_path, transcode_message = transcode_proper_video(folder_path, renamed_video_path, modify=modify)
        print(f'\t{transcode_message}')

        delete_messages = delete_excess_files(folder_path, transcoded_path, modify=modify)
        for message in delete_messages:
            print(f'\t{message}')

        print('\n')

        return True
    except AssertionError:
        return False


def check_proper_folder_name(folder_path):
    folder_name = os.path.basename(folder_path)
    is_proper = re.match(r'^.+ \(20\d\d\)$', folder_name) != None
    return is_proper

def extract_year(folder_path):
    folder_name = os.path.basename(folder_path)
    year_str = re.search(r'\(20\d\d\)', folder_name).group()
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
    new_name = os.path.basename(folder_path)
    _, current_extension = os.path.splitext(video_path)
    new_video_path = os.path.join(folder_path, f'{new_name}{current_extension}')

    if modify:
        os.rename(video_path, new_video_path)
        return (new_video_path, f'[RENAMED] {video_path} to {new_video_path}')
    else:
        return (new_video_path, f'Rename {video_path} to {new_video_path}')

def transcode_proper_video(folder_path, video_path, modify=False):
    current_name, current_extension = os.path.splitext(os.path.basename(video_path))
    if current_extension == PREFERRED_VIDEO_EXTENSION:
        return (video_path, f'{video_path} already encoded as {PREFERRED_VIDEO_EXTENSION}')
    new_video_path = os.path.join(folder_path, f'{current_name}{PREFERRED_VIDEO_EXTENSION}')

    if modify:
        subprocess.run(args=['handbrake', '-i', video_path, '--preset', 'H.264 MKV 1080p30', '-o', new_video_path], check=True)
        return (new_video_path, f'[TRANSCODED] {current_name}{current_extension} to {current_name}{PREFERRED_VIDEO_EXTENSION}')
    else:
        return (new_video_path, f'Transcode {current_name}{current_extension} to {current_name}{PREFERRED_VIDEO_EXTENSION}')

def delete_excess_files(folder_path, proper_video_path, modify=False):
    messages = []
    for dir_entry in os.listdir(folder_path):
        dir_entry_path = os.path.join(folder_path, dir_entry)
        if dir_entry_path != proper_video_path:
            if modify:
                if os.path.isdir(dir_entry_path):
                    os.removedirs(dir_entry_path)
                else:
                    os.remove(dir_entry_path)
                messages.append(f'[DELETED] {dir_entry_path}')
            else:
                messages.append(f'Delete {dir_entry_path}')
    return messages

if __name__ == '__main__':
    main()