// src/extension.ts
import * as vscode from 'vscode';
import * as path from 'path';
import { spawn } from 'child_process';

let outputChannel: vscode.OutputChannel;

export function activate(context: vscode.ExtensionContext) {

    // Create the channel ONCE when the extension is activated
    outputChannel = vscode.window.createOutputChannel("AI Agent");

    let disposable = vscode.commands.registerCommand('ai-project-refactorer.start', () => {
        const panel = vscode.window.createWebviewPanel(
            'aiProjectRefactorer',             // viewType: unique identifier
            'AI Project Refactorer',           // title shown in the tab
            vscode.ViewColumn.One,             // showOptions: open in first column
            {
                enableScripts: true,
                retainContextWhenHidden: true
            }
        );

        panel.webview.html = getWebviewContent();

        panel.webview.onDidReceiveMessage(
            async message => {
                if (message.command === 'submit') {
                    const workspaceFolders = vscode.workspace.workspaceFolders;
                    if (!workspaceFolders) {
                        vscode.window.showErrorMessage('Please open a project folder first!');
                        return;
                    }
                    const projectPath = workspaceFolders[0].uri.fsPath;

                    // Tell the UI we are starting
                    panel.webview.postMessage({ command: 'set-running-state', running: true });

                    try {
                        await vscode.window.withProgress({
                            location: vscode.ProgressLocation.Notification,
                            title: "AI Agent is running...",
                            cancellable: true // Enable cancellation
                        }, (progress, token) => {
                            // Pass the cancellation token to runAgent
                            return runAgent(context, projectPath, message.data, progress, token);
                        });
                    } catch (error) {
                        console.error("Agent run failed", error);
                        // Error messages are already shown in runAgent
                    } finally {
                        // Tell the UI we are finished, no matter what
                        panel.webview.postMessage({ command: 'set-running-state', running: false });
                    }
                }
            },
            undefined,
            context.subscriptions
        );
    });

    context.subscriptions.push(disposable);
}

// UPDATED HELPER FUNCTION TO SETUP PYTHON WITH CONFIGURABLE PATH
async function setupPythonEnvironment(context: vscode.ExtensionContext, progress: vscode.Progress<{ message?: string }>): Promise<string> {
    progress.report({ message: "Setting up Python environment..." });

    // Read the python path from settings, with 'python' as a fallback
    const config = vscode.workspace.getConfiguration('ai-project-refactorer');
    const pythonCommand = config.get<string>('pythonPath') || 'python';

    const agentPath = path.join(context.extensionPath, 'agent');
    const venvPath = path.join(agentPath, '.venv');
    const requirementsPath = path.join(agentPath, 'requirements.txt');

    // Platform-specific paths for Python executable and pip
    const isWindows = process.platform === 'win32';
    const pythonExecutable = isWindows ? path.join(venvPath, 'Scripts', 'python.exe') : path.join(venvPath, 'bin', 'python');
    const pipExecutable = isWindows ? path.join(venvPath, 'Scripts', 'pip.exe') : path.join(venvPath, 'bin', 'pip');

    // Helper function to run commands
    const runCommand = (cmd: string, args: string[]) => new Promise<void>((resolve, reject) => {
        const process = spawn(cmd, args, { cwd: agentPath });
        process.stdout.on('data', data => console.log(`stdout: ${data}`));
        process.stderr.on('data', data => console.error(`stderr: ${data}`));
        process.on('close', code => code === 0 ? resolve() : reject(new Error(`Command failed with code ${code}: ${cmd} ${args.join(' ')}`)));
    });

    try {
        // 1. Check if the virtual environment's Python exists. If not, create it.
        if (!await vscode.workspace.fs.stat(vscode.Uri.file(pythonExecutable)).then(() => true, () => false)) {
            progress.report({ message: "Creating virtual environment..." });
            // Use the configured pythonCommand instead of the hardcoded 'python'
            await runCommand(pythonCommand, ['-m', 'venv', '.venv']);
        }
        
        // 2. Install dependencies from requirements.txt
        progress.report({ message: "Installing dependencies..." });
        await runCommand(pipExecutable, ['install', '-r', requirementsPath]);

        progress.report({ message: "Environment is ready." });
        return pythonExecutable; // Return the full path to the venv Python
    } catch (error) {
        // Provide more specific error messages for common Python setup issues
        const errorMessage = error instanceof Error ? error.message : String(error);
        
        let userMessage = `Failed to set up Python environment: ${errorMessage}`;
        
        if (errorMessage.includes('python')) {
            userMessage = `Python not found. Please check your Python path in settings. Current path: "${pythonCommand}"`;
        } else if (errorMessage.includes('venv')) {
            userMessage = `Failed to create virtual environment. Ensure Python has venv module installed.`;
        } else if (errorMessage.includes('requirements.txt')) {
            userMessage = `Failed to install dependencies. Check if requirements.txt exists and contains valid packages.`;
        }
        
        vscode.window.showErrorMessage(userMessage);
        throw error;
    }
}

// UPDATED runAgent FUNCTION WITH IBM WATSONX.AI ENVIRONMENT VARIABLES
async function runAgent(
    context: vscode.ExtensionContext,
    projectPath: string,
    formData: any,
    progress: vscode.Progress<{ message?: string; increment?: number }>,
    token: vscode.CancellationToken // Add the cancellation token parameter
) {
    try {
        const pythonPath = await setupPythonEnvironment(context, progress);
        const agentPath = path.join(context.extensionPath, 'agent');
        const scriptPath = path.join(agentPath, 'run_agent.py');
        
        const args = [
            scriptPath,
            '--project-path', projectPath,
            '--persona', formData.persona,
            '--pain-points', formData.painPoints,
            '--use-cases', formData.useCases,
            '--success-metrics', formData.successMetrics,
        ];

        // Clear the channel from previous runs and show it to the user
        outputChannel.clear();
        outputChannel.show(true);
        outputChannel.appendLine(">>> Starting AI Agent with IBM Watsonx.ai...");
        outputChannel.appendLine(`>>> Project Path: ${projectPath}`);
        outputChannel.appendLine("---------------------------------------------------\n");

        // Get IBM Watsonx.ai configuration
        const config = vscode.workspace.getConfiguration('ai-project-refactorer');
        const ibmApiKey = config.get<string>('ibmApiKey');
        const ibmUrl = config.get<string>('ibmUrl') || 'https://us-south.ml.cloud.ibm.com';
        const ibmProjectId = config.get<string>('ibmProjectId');

        // Validate IBM credentials
        if (!ibmApiKey || !ibmProjectId) {
            const message = 'Please configure your IBM Watsonx.ai API Key and Project ID in VS Code settings.';
            vscode.window.showErrorMessage(message);
            outputChannel.appendLine(`[ERROR] ${message}`);
            throw new Error(message);
        }
        
        const agentProcess = spawn(pythonPath, args, {
            env: {
                ...process.env,
                'IBM_API_KEY': ibmApiKey,
                'IBM_URL': ibmUrl,
                'IBM_PROJECT_ID': ibmProjectId,
                'PYTHONIOENCODING': 'utf-8'
            },
            cwd: projectPath
        });

        // Listen for the user clicking the "Cancel" button
        token.onCancellationRequested(() => {
            outputChannel.appendLine("\n>>> User requested cancellation. Terminating agent...");
            console.log("User cancelled the agent run.");
            agentProcess.kill('SIGTERM'); // Send the termination signal to the Python process
        });

        return new Promise<void>((resolve, reject) => {
            // Pipe stdout to the output channel with improved progress parsing
            agentProcess.stdout.on('data', (data) => {
                const output = data.toString();
                outputChannel.append(output); // Keep appending raw log for debugging

                // Try to parse the output as JSON for cleaner progress
                try {
                    const lines = output.trim().split('\n');
                    for (const line of lines) {
                        if (line.trim()) {
                            const log = JSON.parse(line);
                            if (log.type === 'progress') {
                                const friendlyMessage = `Phase ${log.phase}: ${log.message}`;
                                progress.report({ message: friendlyMessage });
                            }
                        }
                    }
                } catch (e) {
                    // It's not JSON, so it might be a multi-line message.
                    // Just show the last line in the progress notification.
                    const lastLine = output.trim().split('\n').pop();
                    if (lastLine) {
                        progress.report({ message: lastLine });
                    }
                }
            });

            // Pipe stderr to the output channel
            agentProcess.stderr.on('data', (data) => {
                outputChannel.appendLine(`[ERROR] ${data.toString()}`);
                vscode.window.showErrorMessage(`Agent Error: See the "AI Agent" output channel for details.`);
            });

            agentProcess.on('close', (code) => {
                outputChannel.appendLine("\n---------------------------------------------------");
                
                // If the process was killed because of cancellation, just resolve.
                if (token.isCancellationRequested) {
                    outputChannel.appendLine(">>> AI Agent process was cancelled.");
                    vscode.window.showInformationMessage('AI Agent was cancelled by user.');
                    resolve();
                    return;
                }

                if (code === 0) {
                    outputChannel.appendLine(">>> AI Agent finished successfully!");
                    vscode.window.showInformationMessage('AI Agent finished successfully!');
                    resolve();
                } else {
                    outputChannel.appendLine(`>>> AI Agent process exited with error code ${code}.`);
                    
                    // Provide smarter error messages based on exit codes
                    let userMessage = `Agent process exited with error code ${code}.`;
                    switch (code) {
                        case 2:
                            userMessage = "Agent failed during Phase 1 (Discovery & Strategy). Check the output panel for details.";
                            break;
                        case 3:
                            userMessage = "Agent failed during Phase 2 (Execution & Refactoring). Check the output panel for details.";
                            break;
                        case 4:
                            userMessage = "Agent failed during Phase 3 (Documentation & Verification). Check the output panel for details.";
                            break;
                        case 1:
                            userMessage = "Agent encountered a general error. Check the output panel for details.";
                            break;
                        default:
                            userMessage = `Agent process failed with unexpected error code ${code}. Check the output panel for details.`;
                            break;
                    }
                    
                    vscode.window.showErrorMessage(userMessage);
                    reject(new Error(`Agent process exited with code ${code}`));
                }
            });
        });

    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        outputChannel.appendLine(`[SETUP ERROR] ${errorMessage}`);
        vscode.window.showErrorMessage('Failed to run the agent. Check the output panel for details.');
        throw error;
    }
}

// Updated Webview content with IBM Watsonx.ai branding
function getWebviewContent() {
    return `<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI Project Refactorer</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333;
                min-height: 100vh;
                box-sizing: border-box;
            }
            
            .container {
                max-width: 600px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            }
            
            .header {
                text-align: center;
                margin-bottom: 30px;
            }
            
            .header h1 {
                margin: 0;
                font-size: 2.5em;
                font-weight: 700;
                background: linear-gradient(45deg, #667eea, #764ba2);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            
            .header p {
                margin: 10px 0 0 0;
                color: #666;
                font-size: 1.1em;
            }

            .powered-by {
                text-align: center;
                margin-bottom: 20px;
                padding: 10px;
                background: linear-gradient(45deg, #1f4037, #99f2c8);
                color: white;
                border-radius: 10px;
                font-weight: 600;
            }
            
            .form-group {
                margin-bottom: 25px;
            }
            
            .form-group label {
                display: block;
                margin-bottom: 8px;
                font-weight: 600;
                color: #555;
            }
            
            .form-group input, .form-group select, .form-group textarea {
                width: 100%;
                padding: 12px 16px;
                border: 2px solid #e0e0e0;
                border-radius: 10px;
                font-size: 14px;
                transition: all 0.3s ease;
                box-sizing: border-box;
            }
            
            .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }
            
            .form-group textarea {
                resize: vertical;
                min-height: 80px;
            }
            
            .submit-btn {
                width: 100%;
                padding: 16px;
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            
            .submit-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
            }
            
            .submit-btn:active {
                transform: translateY(0);
            }
            
            .submit-btn:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }
            
            .running-message {
                display: none;
                text-align: center;
                padding: 20px;
                background: linear-gradient(45deg, #ffecd2, #fcb69f);
                border-radius: 12px;
                margin-top: 20px;
                font-weight: 600;
                color: #8b4513;
            }
            
            .info-box {
                background: linear-gradient(45deg, #a8edea, #fed6e3);
                padding: 20px;
                border-radius: 12px;
                margin-bottom: 25px;
                font-size: 14px;
                line-height: 1.5;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Velora Agent</h1>
                <p>Intelligent Python Project Refactoring</p>
            </div>

            <div class="powered-by">
                🚀 Powered by IBM Watsonx.ai
            </div>
            
            <div class="info-box">
                <strong>🎯 What this agent does:</strong><br>
                • Analyzes your messy project structure<br>
                • Creates a clean, organized file hierarchy<br>
                • Generates comprehensive documentation<br>
                • Fixes imports and dependencies<br>
                • Provides professional README files
            </div>
            
            <form id="refactorForm">
                <div class="form-group">
                    <label for="persona">👤 I am a...</label>
                    <select id="persona" required>
                        <option value="">Select your role</option>
                        <option value="Developer">Developer</option>
                        <option value="Data Scientist">Data Scientist</option>
                        <option value="Researcher">Researcher</option>
                        <option value="Student">Student</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="painPoints">😤 Current problems (comma-separated)</label>
                    <textarea id="painPoints" placeholder="e.g., messy imports, no structure, hard to navigate, missing docs" required></textarea>
                </div>
                
                <div class="form-group">
                    <label for="useCases">🎯 What should the agent do? (comma-separated)</label>
                    <textarea id="useCases" placeholder="e.g., create src folder, organize modules, add documentation, fix imports" required></textarea>
                </div>
                
                <div class="form-group">
                    <label for="successMetrics">📊 How will you measure success?</label>
                    <input type="text" id="successMetrics" placeholder="A clean, navigable project with good documentation" />
                </div>
                
                <button type="submit" class="submit-btn" id="submitBtn">
                    🚀 Transform My Project
                </button>
            </form>
            
            <div class="running-message" id="runningMessage">
                🔄 AI Agent is analyzing and refactoring your project...<br>
                Check the "AI Agent" output panel for live progress updates.
            </div>
        </div>

        <script>
            const vscode = acquireVsCodeApi();
            
            document.getElementById('refactorForm').addEventListener('submit', function(e) {
                e.preventDefault();
                
                const formData = {
                    persona: document.getElementById('persona').value,
                    painPoints: document.getElementById('painPoints').value,
                    useCases: document.getElementById('useCases').value,
                    successMetrics: document.getElementById('successMetrics').value || 'A functional, easy-to-navigate project structure.'
                };
                
                vscode.postMessage({
                    command: 'submit',
                    data: formData
                });
            });
            
            window.addEventListener('message', event => {
                const message = event.data;
                
                if (message.command === 'set-running-state') {
                    const runningMessage = document.getElementById('runningMessage');
                    const submitBtn = document.getElementById('submitBtn');
                    
                    if (message.running) {
                        runningMessage.style.display = 'block';
                        submitBtn.disabled = true;
                        submitBtn.textContent = '⏳ Processing...';
                    } else {
                        runningMessage.style.display = 'none';
                        submitBtn.disabled = false;
                        submitBtn.textContent = '🚀 Transform My Project';
                    }
                }
            });
        </script>
    </body>
    </html>`;
}

export function deactivate() {}