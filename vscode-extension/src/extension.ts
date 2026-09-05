import * as vscode from 'vscode';

const FRONTEND_URL = 'http://localhost:5173';
const BACKEND_URL = 'http://127.0.0.1:8000';

/**
 * Builds the HTML shown inside the "Ashlar" sidebar webview.
 *
 * The webview simply embeds the existing Vite/React frontend (served at
 * FRONTEND_URL) in an <iframe>. A plain-text fallback notice is rendered
 * above the iframe (outside of it) so it's visible even if the iframe
 * itself fails to load because the backend/frontend dev servers aren't
 * running yet.
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
    #fallback-notice {
      box-sizing: border-box;
      padding: 6px 10px;
      font-size: 12px;
      line-height: 1.4;
      border-bottom: 1px solid var(--vscode-panel-border, #444);
    }
    #ashlar-frame {
      display: block;
      width: 100%;
      height: calc(100% - 44px);
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
</body>
</html>`;
}

class AshlarSidebarViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'ashlar.sidebar';

  public resolveWebviewView(webviewView: vscode.WebviewView): void {
    webviewView.webview.options = {
      enableScripts: true,
    };
    webviewView.webview.html = getWebviewHtml();
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
