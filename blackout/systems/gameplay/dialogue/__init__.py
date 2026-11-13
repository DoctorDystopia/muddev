"""
The dialogue scripts (DESIGN-0017). An author writes a dialogue script in the
Godot editor. The script export compiles it. This package reads the compiled
script and runs it on the server.

Nothing imports this package as a whole. Import the module that you need:
`runner` for a conversation, `loader` for a compiled script by its key,
`checks` for the content rules, and `vocabulary` to add a vocabulary entry.
"""
