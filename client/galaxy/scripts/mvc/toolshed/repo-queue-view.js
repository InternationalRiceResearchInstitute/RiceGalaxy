define(['toolshed/repository-queue-model'], function() {

    var ToolShedRepositoryQueue = Backbone.View.extend({

        el: '#category_list',

        render: function(options) {
            this.options = _.extend(this.options, options);
            var repository_queue_template = this.templateRepoQueue();
            this.$el.html(repository_queue_template({repository: this.model}));
        },

        templateRepoQueueTab: _.template([
            '<li class="nav-tab" role="presentation" id="repository_installation_queue">',
                '<a href="#repository_queue" data-toggle="tab">Repository Installation Queue</a>',
            '</li>',
        ].join('')),

        templateRepoQueue: _.template([
            '<div class="tab-pane" id="repository_queue">',
                '<table id="queued_repositories" class="grid" border="0" cellpadding="2" cellspacing="2" width="100%">',
                    '<thead id="grid-table-header">',
                        '<tr>',
                            '<th class="datasetRow"><input class="btn btn-primary" type="submit" id="install_all" name="install_all" value="Install all" /></th>',
                            '<th class="datasetRow"><input class="btn btn-primary" type="submit" id="clear_queue" name="clear_queue" value="Clear queue" /></th>',
                            '<th class="datasetRow">ToolShed</th>',
                            '<th class="datasetRow">Name</th>',
                            '<th class="datasetRow">Owner</th>',
                            '<th class="datasetRow">Revision</th>',
                        '</tr>',
                    '</thead>',
                    '<tbody>',
                        '<\% _.each(repositories, function(repository) { \%>',
                            '<tr id="queued_repository_<\%= repository.id \%>">',
                                '<td class="datasetRow">',
                                    '<input class="btn btn-primary install_one" data-repokey="<\%= repository.queue_key \%>" type="submit" id="install_repository_<\%= repository.id \%>" name="install_repository" value="Install now" />',
                                '</td>',
                                '<td class="datasetRow">',
                                    '<input class="btn btn-primary remove_one" data-repokey="<\%= repository.queue_key \%>" type="submit" id="unqueue_repository_<\%= repository.id \%>" name="unqueue_repository" value="Remove from queue" />',
                                '</td>',
                                '<td class="datasetRow"><\%= repository.tool_shed_url \%></td>',
                                '<td class="datasetRow"><\%= repository.name \%></td>',
                                '<td class="datasetRow"><\%= repository.owner \%></td>',
                                '<td class="datasetRow"><\%= repository.changeset \%></td>',
                            '</tr>',
                        '<\% }); \%>',
                    '</tbody>',
                '</table>',
                '<input type="button" class="btn btn-primary" id="from_workflow" value="Add from workflow" />',
            '</div>',
        ].join('')),

        workflows_missing_tools: _.template([
            '<table id="workflows_missing_tools" class="grid" border="0" cellpadding="2" cellspacing="2" width="100%">',
                '<thead id="grid-table-header">',
                    '<tr>',
                        '<th class="datasetRow">Workflows</th>',
                        '<th class="datasetRow">Tool IDs</th>',
                        '<th class="datasetRow">Shed</th>',
                        '<th class="datasetRow">Name</th>',
                        '<th class="datasetRow">Owner</th>',
                        '<th class="datasetRow">Actions</th>',
                    '</tr>',
                '</thead>',
                '<tbody>',
                    '<\% _.each(Object.keys(workflows), function(workflow_key) { \%>',
                        '<\% var workflow_details = workflow_key.split("/"); \%>',
                        '<\% var workflow = workflows[workflow_key]; \%>',
                        '<tr>',
                            '<td class="datasetRow">',
                                '<ul class="workflow_names">',
                                    '<\% _.each(workflow.workflows.sort(), function(wf) { \%>',
                                        '<li class="workflow_names"><\%= wf \%></li>',
                                    '<\% }); \%>',
                                '</ul>',
                            '</td>',
                            '<td class="datasetRow">',
                                '<ul class="workflow_tools">',
                                    '<\% _.each(workflow.tools.sort(), function(tool) { \%>',
                                        '<li class="workflow_tools"><\%= tool \%></li>',
                                    '<\% }); \%>',
                                '</ul>',
                            '</td>',
                            '<td class="datasetRow"><\%= workflow_details[0] \%></td>',
                            '<td class="datasetRow"><\%= workflow_details[2] \%></td>',
                            '<td class="datasetRow"><\%= workflow_details[1] \%></td>',
                            '<td class="datasetRow">',
                                '<ul class="workflow_tools">',
                                    '<li class="workflow_tools"><input type="button" class="show_wf_repo btn btn-primary" data-shed="<\%= workflow_details[0] \%>" data-owner="<\%= workflow_details[1] \%>" data-repo="<\%= workflow_details[2] \%>" data-toolids="<\%= workflow.tools.join(",") \%>" value="Preview" /></li>',
                                    '<li><input type="button" class="queue_wf_repo btn btn-primary" data-shed="<\%= workflow_details[0] \%>" data-owner="<\%= workflow_details[1] \%>" data-repo="<\%= workflow_details[2] \%>" data-toolids="<\%= workflow.tools.join(",") \%>" value="Add to queue" /></li>',
                                '</ul>',
                            '</td>',
                        '</tr>',
                    '<\% }); \%>',
                '</ul>',
            '</div>',
        ].join(''))
    });

    return {
        RepoQueue: ToolShedRepositoryQueue,
    };

});
