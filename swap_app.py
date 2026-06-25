#!/usr/bin/env python3

"""
A small, standalone web app for FaceFusion.

One screen: pick a source face, pick a target photo or video, press Swap.
It drives FaceFusion's own `headless-run` pipeline, so results are identical
to the command line - just far easier to use.

	python swap_app.py            # opens http://127.0.0.1:7870
	python swap_app.py --help     # host / port / share options
"""

import argparse
import os
import subprocess
import sys
import tempfile
import uuid
from typing import Any, List, Optional, Tuple

VIDEO_EXTENSIONS = { '.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v', '.gif' }
OUTPUT_DIRECTORY = os.path.join(tempfile.gettempdir(), 'facefusion-swap-outputs')
DEFAULT_FACE_SWAPPER_MODEL = 'hyperswap_1a_256'


def get_face_swapper_models() -> List[str]:
	try:
		from facefusion.processors.modules.face_swapper import choices
		return list(choices.face_swapper_models)
	except Exception:
		return [ DEFAULT_FACE_SWAPPER_MODEL ]


def get_execution_providers() -> List[str]:
	try:
		from facefusion.execution import get_available_execution_providers
		return get_available_execution_providers()
	except Exception:
		return [ 'cpu' ]


def make_output_path(extension : str) -> str:
	os.makedirs(OUTPUT_DIRECTORY, exist_ok = True)
	return os.path.join(OUTPUT_DIRECTORY, uuid.uuid4().hex + extension)


def build_command(source_path : str, target_path : str, output_path : str, processors : List[str], execution_providers : List[str], face_swapper_model : Optional[str]) -> List[str]:
	command = [ sys.executable, 'facefusion.py', 'headless-run' ]
	command += [ '-s', source_path ]
	command += [ '-t', target_path ]
	command += [ '-o', output_path ]
	command += [ '--processors' ] + processors

	if execution_providers:
		command += [ '--execution-providers' ] + execution_providers
	if face_swapper_model:
		command += [ '--face-swapper-model', face_swapper_model ]
	return command


def execute_command(command : List[str]) -> Tuple[int, str]:
	process = subprocess.run(command, stdout = subprocess.PIPE, stderr = subprocess.STDOUT, text = True)
	return process.returncode, process.stdout


def summarize_log(log : str) -> str:
	log = (log or '').strip()

	if not log:
		return 'The swap failed without any output. Make sure FaceFusion is installed and ffmpeg is available.'
	lines = [ line for line in log.splitlines() if line.strip() ]
	highlighted = [ line for line in lines if any(token in line.lower() for token in [ 'error', 'not installed', 'unable', 'no face', 'failed' ]) ]
	return '\n'.join((highlighted or lines)[-8:])[-1500:]


def perform_swap(source_path : Optional[str], target_path : Optional[str], enhance : bool, execution_provider : Optional[str], face_swapper_model : Optional[str]) -> Tuple[str, bool]:
	if not source_path:
		raise ValueError('Please add a source face image.')
	if not target_path:
		raise ValueError('Please add a target photo or video.')

	processors = [ 'face_swapper' ] + ([ 'face_enhancer' ] if enhance else [])
	execution_providers = [ execution_provider ] if execution_provider else []
	extension = os.path.splitext(target_path)[1].lower() or '.jpg'
	output_path = make_output_path(extension)
	command = build_command(source_path, target_path, output_path, processors, execution_providers, face_swapper_model)
	return_code, log = execute_command(command)

	if return_code != 0 or not os.path.isfile(output_path):
		raise ValueError(summarize_log(log))
	return output_path, extension in VIDEO_EXTENSIONS


def create_app() -> Any:
	import gradio

	models = get_face_swapper_models()
	providers = get_execution_providers()
	default_model = DEFAULT_FACE_SWAPPER_MODEL if DEFAULT_FACE_SWAPPER_MODEL in models else (models[0] if models else None)

	def on_swap(source_path, target_path, enhance, execution_provider, face_swapper_model, progress = gradio.Progress()):
		progress(0.05, desc = 'Preparing')
		try:
			output_path, is_video = perform_swap(source_path, target_path, enhance, execution_provider, face_swapper_model)
		except ValueError as exception:
			raise gradio.Error(str(exception))
		progress(1.0, desc = 'Done')
		return (
			gradio.update(value = None if is_video else output_path, visible = not is_video),
			gradio.update(value = output_path if is_video else None, visible = is_video),
			gradio.update(value = output_path, visible = True)
		)

	with gradio.Blocks(title = 'FaceFusion - Simple Swap', theme = gradio.themes.Base(primary_hue = 'red', neutral_hue = 'neutral')) as app:
		gradio.Markdown('# FaceFusion · Simple Face Swap\nAdd a **source face**, add a **target photo or video**, then press **Swap face**.')

		with gradio.Row():
			source_component = gradio.Image(label = '1 · Source face', type = 'filepath', sources = [ 'upload', 'webcam' ], height = 320)
			target_component = gradio.File(label = '2 · Target photo or video', file_types = [ 'image', 'video' ], type = 'filepath', height = 320)

		enhance_component = gradio.Checkbox(label = 'Enhance the result (sharper, cleaner faces)', value = False)

		with gradio.Accordion('Advanced', open = False):
			provider_component = gradio.Dropdown(label = 'Run on', choices = providers, value = providers[0] if providers else None)
			model_component = gradio.Dropdown(label = 'Face swapper model', choices = models, value = default_model)

		run_component = gradio.Button('Swap face', variant = 'primary', size = 'lg')

		result_image_component = gradio.Image(label = 'Result', visible = False)
		result_video_component = gradio.Video(label = 'Result', visible = False)
		result_file_component = gradio.File(label = 'Download result', visible = False)

		gradio.Markdown('_First run downloads the required models, so it can take a little while. Videos need ffmpeg installed and take longer than photos._')

		run_component.click(
			fn = on_swap,
			inputs = [ source_component, target_component, enhance_component, provider_component, model_component ],
			outputs = [ result_image_component, result_video_component, result_file_component ]
		)
	return app


def main() -> None:
	parser = argparse.ArgumentParser(description = 'A simple standalone face-swap web app for FaceFusion.')
	parser.add_argument('--host', default = '127.0.0.1', help = 'host to bind (default: 127.0.0.1)')
	parser.add_argument('--port', type = int, default = 7870, help = 'port to listen on (default: 7870)')
	parser.add_argument('--share', action = 'store_true', help = 'create a public Gradio share link')
	parser.add_argument('--no-browser', action = 'store_true', help = 'do not open a browser automatically')
	arguments = parser.parse_args()

	app = create_app()
	app.launch(
		server_name = arguments.host,
		server_port = arguments.port,
		share = arguments.share,
		inbrowser = not arguments.no_browser,
		allowed_paths = [ OUTPUT_DIRECTORY ],
		show_api = False
	)


if __name__ == '__main__':
	main()
