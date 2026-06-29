import os
import shutil

import pytest
import swap_app


def test_build_command() -> None:
	command = swap_app.build_command('face.jpg', 'scene.mp4', 'out.mp4', [ 'face_swapper', 'face_enhancer' ], [ 'cuda' ], 'inswapper_128')

	assert 'facefusion.py' in command
	assert 'headless-run' in command
	assert command[command.index('-s') + 1] == 'face.jpg'
	assert command[command.index('-t') + 1] == 'scene.mp4'
	assert command[command.index('-o') + 1] == 'out.mp4'
	assert command[command.index('--processors') + 1:command.index('--processors') + 3] == [ 'face_swapper', 'face_enhancer' ]
	assert command[command.index('--execution-providers') + 1] == 'cuda'
	assert command[command.index('--face-swapper-model') + 1] == 'inswapper_128'


def test_build_command_minimal() -> None:
	command = swap_app.build_command('face.jpg', 'photo.jpg', 'out.jpg', [ 'face_swapper' ], [], None)

	assert '--execution-providers' not in command
	assert '--face-swapper-model' not in command
	assert command[command.index('--processors') + 1] == 'face_swapper'


def test_perform_swap_requires_inputs() -> None:
	with pytest.raises(ValueError):
		swap_app.perform_swap(None, 'photo.jpg', False, 'cpu', 'hyperswap_1a_256')
	with pytest.raises(ValueError):
		swap_app.perform_swap('face.jpg', None, False, 'cpu', 'hyperswap_1a_256')


def test_perform_swap_photo(monkeypatch, tmp_path) -> None:
	target_path = str(tmp_path / 'photo.jpg')
	with open(target_path, 'wb') as target_file:
		target_file.write(b'PHOTO-PIXELS')

	def fake_execute(command):
		# simulate a successful FaceFusion run by writing the target through to the output
		shutil.copy(command[command.index('-t') + 1], command[command.index('-o') + 1])
		return 0, 'processing succeeded'

	monkeypatch.setattr(swap_app, 'execute_command', fake_execute)
	output_path, is_video = swap_app.perform_swap('face.jpg', target_path, False, 'cpu', 'hyperswap_1a_256')

	assert is_video is False
	assert os.path.isfile(output_path)
	with open(output_path, 'rb') as output_file:
		assert output_file.read() == b'PHOTO-PIXELS'


def test_perform_swap_video_with_enhance(monkeypatch, tmp_path) -> None:
	target_path = str(tmp_path / 'clip.mp4')
	with open(target_path, 'wb') as target_file:
		target_file.write(b'VIDEO-BYTES')
	captured = {}

	def fake_execute(command):
		captured['command'] = command
		shutil.copy(command[command.index('-t') + 1], command[command.index('-o') + 1])
		return 0, ''

	monkeypatch.setattr(swap_app, 'execute_command', fake_execute)
	output_path, is_video = swap_app.perform_swap('face.jpg', target_path, True, 'cpu', 'hyperswap_1a_256')

	assert is_video is True
	assert output_path.endswith('.mp4')
	assert 'face_enhancer' in captured['command']


def test_perform_swap_failure_surfaces_log(monkeypatch, tmp_path) -> None:
	target_path = str(tmp_path / 'photo.jpg')
	with open(target_path, 'wb') as target_file:
		target_file.write(b'x')

	monkeypatch.setattr(swap_app, 'execute_command', lambda command: (1, 'ERROR: ffmpeg is not installed'))
	with pytest.raises(ValueError) as exception:
		swap_app.perform_swap('face.jpg', target_path, False, 'cpu', 'hyperswap_1a_256')
	assert 'ffmpeg' in str(exception.value)


def test_summarize_log_highlights_errors() -> None:
	log = 'INFO loading\nINFO detecting\nERROR no face detected in source\nINFO cleanup'
	assert 'no face detected' in swap_app.summarize_log(log)
	assert swap_app.summarize_log('') != ''
