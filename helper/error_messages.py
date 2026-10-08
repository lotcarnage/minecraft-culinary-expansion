"""Japanese messages for editor dialogs, including library and filesystem errors."""
import json
import logging
import re
import struct
import tkinter as tk
import zipfile


def japanese_error(error):
    if isinstance(error, json.JSONDecodeError):
        return f'JSONの書式が正しくありません。{error.lineno}行目、{error.colno}文字目を確認してください。'
    path=getattr(error,'filename',None)
    suffix=f'\n対象ファイル: {path}' if path else ''
    if isinstance(error, FileNotFoundError):
        return '必要なファイルまたはフォルダーが見つかりません。'+suffix
    if isinstance(error, PermissionError):
        return 'ファイルにアクセスできません。アクセス権限や、他のアプリで使用中でないか確認してください。'+suffix
    if isinstance(error, UnicodeError):
        return 'ファイルの文字コードを読み取れません。UTF-8形式で保存してください。'
    if isinstance(error, OSError):
        return 'ファイルの読み書きに失敗しました。保存先や空き容量を確認してください。'+suffix
    if isinstance(error, zipfile.BadZipFile):
        return '指定したJARまたはZIPファイルが破損しているか、形式が正しくありません。'
    if isinstance(error, struct.error):
        return '画像ファイルの情報を読み取れません。正常なPNGファイルを指定してください。'
    if isinstance(error, tk.TclError):
        return '画面や画像の処理に失敗しました。画像の形式を確認し、必要に応じてエディターを開き直してください。'
    if isinstance(error, KeyError):
        return f'必要なデータ項目がありません。項目: {error.args[0]}'
    message=str(error)
    if isinstance(error, ValueError) and re.search(r'[ぁ-んァ-ヶ一-龯]',message):
        return message
    logging.getLogger(__name__).error('Editor operation failed',exc_info=(type(error),error,error.__traceback__))
    if isinstance(error,(ValueError,TypeError)):
        return '入力値またはファイルのデータ形式が正しくありません。入力内容と指定ファイルを確認してください。'
    return '処理中に予期しないエラーが発生しました。エディターを起動した端末のエラー情報を確認してください。'
