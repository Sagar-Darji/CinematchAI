#!/usr/bin/env bash
# Tab completion setup script for cinematch CLI
# Usage: source scripts/install-completion.sh

echo "🎬 CinematchAI CLI - Tab Completion Installer"
echo ""

# Detect shell
SHELL_NAME=$(basename "$SHELL")

case "$SHELL_NAME" in
    bash)
        echo "Installing for Bash..."
        COMPLETION_DIR="$HOME/.bash_completion.d"
        RC_FILE="$HOME/.bashrc"
        
        mkdir -p "$COMPLETION_DIR"
        
        # Generate completion
        _CINEMATCH_COMPLETE=bash_source cinematch > "$COMPLETION_DIR/cinematch" 2>/dev/null
        
        # Add to bashrc if not already there
        if ! grep -q "cinematch completion" "$RC_FILE" 2>/dev/null; then
            echo "" >> "$RC_FILE"
            echo "# cinematch completion" >> "$RC_FILE"
            echo "[ -f ~/.bash_completion.d/cinematch ] && source ~/.bash_completion.d/cinematch" >> "$RC_FILE"
            echo "✅ Added to $RC_FILE"
        else
            echo "✅ Already in $RC_FILE"
        fi
        
        echo "✅ Bash completion installed!"
        echo "Run: source ~/.bashrc"
        ;;
        
    zsh)
        echo "Installing for Zsh..."
        COMPLETION_DIR="${fpath[1]}"
        RC_FILE="$HOME/.zshrc"
        
        # Add to zshrc if not already there
        if ! grep -q "cinematch completion" "$RC_FILE" 2>/dev/null; then
            echo "" >> "$RC_FILE"
            echo "# cinematch completion" >> "$RC_FILE"
            echo 'eval "$(_CINEMATCH_COMPLETE=zsh_source cinematch)"' >> "$RC_FILE"
            echo "✅ Added to $RC_FILE"
        else
            echo "✅ Already in $RC_FILE"
        fi
        
        echo "✅ Zsh completion installed!"
        echo "Run: source ~/.zshrc"
        ;;
        
    fish)
        echo "Installing for Fish..."
        COMPLETION_DIR="$HOME/.config/fish/completions"
        mkdir -p "$COMPLETION_DIR"
        
        _CINEMATCH_COMPLETE=fish_source cinematch > "$COMPLETION_DIR/cinematch.fish" 2>/dev/null
        
        echo "✅ Fish completion installed!"
        echo "Run: source ~/.config/fish/config.fish"
        ;;
        
    *)
        echo "❌ Unsupported shell: $SHELL_NAME"
        echo "Supported: bash, zsh, fish"
        exit 1
        ;;
esac

echo ""
echo "🎉 Tab completion ready! Try:"
echo "   cinematch <TAB>"
echo "   cinematch enrichment <TAB>"
