import * as vscode from 'vscode';

const FRONTEND_URL = 'http://localhost:5173';
const BACKEND_URL = 'http://127.0.0.1:8000';

/**
 * The `--vscode-*` CSS custom properties VS Code injects into every
 * webview's own top-level document. These are NOT visible inside the
 * <iframe> (it's a separate document loaded from a different origin --
 * cross-origin documents never share a CSSOM), so the outer webview
 * script reads them here and relays them into the iframe via
 * postMessage. This is the only way the embedded frontend can actually
 * match the user's live VS Code theme rather than guess at one.
 */
const THEME_VAR_NAMES = [
  '--vscode-font-family',
  '--vscode-editor-font-family',
  '--vscode-editor-background',
  '--vscode-foreground',
  '--vscode-descriptionForeground',
  '--vscode-panel-border',
  '--vscode-widget-border',
  '--vscode-input-background',
  '--vscode-input-border',
  '--vscode-input-foreground',
  '--vscode-button-background',
  '--vscode-button-foreground',
  '--vscode-button-hoverBackground',
  '--vscode-focusBorder',
  '--vscode-textLink-foreground',
  '--vscode-textCodeBlock-background',
  '--vscode-editorWidget-background',
  '--vscode-charts-red',
  '--vscode-charts-green',
  '--vscode-charts-yellow',
  '--vscode-errorForeground',
];

/**
 * Builds the HTML shown inside the "Ashlar" sidebar webview.
 *
 * The webview embeds the existing Vite/React frontend (served at
 * FRONTEND_URL) in an <iframe>, plus a small bridge script with two
 * jobs:
 *   1. Relay VS Code's live theme variables into the iframe (see
 *      THEME_VAR_NAMES above), re-sending whenever the theme changes.
 *   2. Relay "insert this code into the editor" requests the other
 *      direction: iframe -> this script -> the real VS Code extension
 *      host (via acquireVsCodeApi(), the only channel a webview has
 *      back to the extension) -> resolveWebviewView's message handler,
 *      which actually edits the active text editor.
 */
function getWebviewHtml(): string {
  return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta
    http-equiv="Content-Security-Policy"
    content="default-src 'none'; frame-src ${FRONTEND_URL}; connect-src ${FRONTEND_URL} ${BACKEND_URL}; style-src 'unsafe-inline'; img-src ${FRONTEND_URL} data:;"
  />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    html, body {
      margin: 0;
      padding: 0;
      height: 100%;
      width: 100%;
      overflow: hidden;
      font-family: var(--vscode-font-family, sans-serif);
      color: var(--vscode-foreground);
      background-color: var(--vscode-editor-background);
    }
    body {
      display: flex;
      flex-direction: column;
    }
    #fallback-notice {
      box-sizing: border-box;
      flex: none;
      padding: 6px 10px;
      font-size: 12px;
      line-height: 1.4;
      border-bottom: 1px solid var(--vscode-panel-border, #444);
    }
    #ashlar-frame {
      display: block;
      flex: 1;
      width: 100%;
      border: none;
    }
  </style>
</head>
<body>
  <div id="fallback-notice">
    If this is blank, the Ashlar backend isn't running yet &mdash; see the command
    "Ashlar: Open in Browser" or run <code>uv run python -m ashlar.api.server</code>
    and <code>npm run dev</code> in the <code>frontend/</code> directory first.
  </div>
  <iframe
    id="ashlar-frame"
    src="${FRONTEND_URL}"
    sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
  ></iframe>
  <script>
    const vscodeApi = acquireVsCodeApi();
    const frame = document.getElementById('ashlar-frame');
    const themeVarNames = ${JSON.stringify(THEME_VAR_NAMES)};

    function currentThemeKind() {
      const cls = document.body.className;
      if (cls.indexOf('vscode-high-contrast') !== -1) return 'high-contrast';
      if (cls.indexOf('vscode-dark') !== -1) return 'dark';
      return 'light';
    }

    function sendTheme() {
      const computed = getComputedStyle(document.documentElement);
      const vars = {};
      for (const name of themeVarNames) {
        const value = computed.getPropertyValue(name).trim();
        if (value) vars[name] = value;
      }
      frame.contentWindow.postMessage(
        { source: 'ashlar-vscode-host', type: 'theme', kind: currentThemeKind(), vars },
        '*',
      );
    }

    // Initial theme send once the frontend has loaded and can receive it.
    frame.addEventListener('load', sendTheme);

    // VS Code signals a theme change by swapping the body's
    // vscode-light/vscode-dark/vscode-high-contrast class -- watch for
    // that and re-send so a live theme switch doesn't require reopening
    // the panel.
    new MutationObserver(sendTheme).observe(document.body, { attributes: true, attributeFilter: ['class'] });

    // The other direction: the embedded app asks to insert generated
    // code into the real editor. Only accept messages that actually
    // came from our own iframe.
    window.addEventListener('message', (event) => {
      if (event.source !== frame.contentWindow) return;
      const data = event.data;
      if (!data || data.source !== 'ashlar-webapp') return;
      vscodeApi.postMessage(data);
    });
  </script>
</body>
</html>`;
}

// The frontend passes the active corpus's real file extension (e.g.
// ".cbl", ".plth", ".m") -- not a VS Code language id, since it has no
// reliable way to know what language id (if any) is registered for a
// given corpus on this machine. Best-effort map a couple of extensions
// we know real, commonly-installed extensions register; anything else
// (including invented DSLs like PLINTH's .plth) falls back to
// undefined, which VS Code opens as plain text -- never an error, just
// no syntax highlighting.
const EXTENSION_TO_LANGUAGE_ID: Record<string, string> = {
  '.cbl': 'cobol',
  '.m': 'mumps',
};

async function insertCodeIntoEditor(code: string, fileExtension?: string): Promise<void> {
  const languageId = fileExtension ? EXTENSION_TO_LANGUAGE_ID[fileExtension] : undefined;
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    const doc = await vscode.workspace.openTextDocument({ content: code, language: languageId });
    await vscode.window.showTextDocument(doc);
    return;
  }
  const selection = editor.selection;
  await editor.edit((editBuilder) => {
    if (selection.isEmpty) {
      editBuilder.insert(selection.active, code);
    } else {
      editBuilder.replace(selection, code);
    }
  });
  void vscode.window.showInformationMessage('Ashlar: inserted generated code into the active editor.');
}

class AshlarSidebarViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'ashlar.sidebar';

  public resolveWebviewView(webviewView: vscode.WebviewView): void {
    webviewView.webview.options = {
      enableScripts: true,
    };
    webviewView.webview.html = getWebviewHtml();

    webviewView.webview.onDidReceiveMessage((message: { type?: string; code?: string; extension?: string }) => {
      if (message?.type === 'insert-code' && typeof message.code === 'string') {
        void insertCodeIntoEditor(message.code, message.extension);
      }
    });
  }
}

export function activate(context: vscode.ExtensionContext): void {
  const provider = new AshlarSidebarViewProvider();

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      AshlarSidebarViewProvider.viewType,
      provider,
    ),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('ashlar.openAssistant', async () => {
      await vscode.commands.executeCommand('ashlar.sidebar.focus');
    }),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('ashlar.openInBrowser', async () => {
      await vscode.env.openExternal(vscode.Uri.parse(FRONTEND_URL));
    }),
  );
}

export function deactivate(): void {
  // No cleanup required.
}
