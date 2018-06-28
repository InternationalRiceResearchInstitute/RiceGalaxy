<%inherit file="/base.mako"/>
<%namespace name="grid_base" file="/grid_base.mako" import="*" />
<%namespace name="grid_common" file="../common/grid_common.mako" import="*" />

<%def name="insert()">
<%
    from tool_shed.grids.repository_grids import ValidRepositoryGrid
    repo_grid = ValidRepositoryGrid()
    grid_common.render_grid_filters(repo_grid)
%>
</%def>

${grid_base.load(False, capture(self.insert))}
