@tool
class_name GearWorkbench
extends FigureWorkbench
## The node of the gear editor scene (DESIGN-0014 section 22). It is a
## [FigureWorkbench] with another name, so the two plugins tell the two
## scenes apart: the gear plugin edits a [GearWorkbench], and the figure
## plugin edits each other [FigureWorkbench].
##
## The stands, the store, the outfit, and the pick are those of the figure
## workbench. The two scenes read and write the same figure files. A
## plugin that takes a scene again reads the files again when the other
## scene wrote them ([method FigureWorkbench.reload_if_changed]).
