define(['mvc/toolshed/toolshed-model', 'mvc/toolshed/util'], function(toolshed_model, toolshed_util) {

    var ToolShedCategoryContentsView = Backbone.View.extend({

        el: '#center',

        initialize: function(params) {
            var self = this;
            this.model = new toolshed_model.CategoryCollection();
            this.listenTo(this.model, 'sync', this.render);
            var shed = params.tool_shed.replace(/\//g, '%2f');
            this.model.url += '?tool_shed_url=' + shed + '&category_id=' + params.category_id;
            this.model.tool_shed = shed;
            this.model.category = params.category_id;
            this.model.fetch();
        },

        render: function(options) {
            this.options = _.extend(this.options, options);
            var category_contents_template = this.templateCategoryContents;
            this.$el.html(category_contents_template({category: this.model.models[0], tool_shed: this.model.tool_shed, queue: toolshed_util.queueLength()}));
            $("#center").css('overflow', 'auto');
            this.bindEvents();
        },

        bindEvents: function() {
            var that = this;
            require(['libs/jquery/jquery-ui'], function() {
                $("#search_box").autocomplete({
                    source: function(request, response) {
                        var shed_url = that.model.tool_shed.replace(/%2f/g, '/');
                        var base_url = Galaxy.root + 'api/tool_shed/search';
                        var params = {term: request.term, tool_shed_url: shed_url};
                        $.post(base_url, params, function(data) {
                            var result_list = toolshed_util.shedParser(data);
                            response(result_list);
                        });
                    },
                    minLength: 3,
                    select: function(event, ui) {
                        var tsr_id = ui.item.value;
                        var new_route = 'repository/s/' + that.model.tool_shed + '/r/' + tsr_id;
                        Backbone.history.navigate(new_route, {trigger: true, replace:true});
                    },
                });
            });
        },

        reDraw: function(options){
            this.$el.empty();
            this.initialize(options);
        },

        templateCategoryContents: _.template([
            '<style type="text/css">',
                '.ui-autocomplete { background-color: #fff; }',
                'li.ui-menu-item { list-style-type: none; }',
            '</style>',
            '<div class="unified-panel-header" id="panel_header" unselectable="on">',
                '<div class="unified-panel-header-inner">Repositories in <%= category.get("name") %></div>',
                '<div class="unified-panel-header-inner" style="position: absolute; right: 5px; top: 0px;"><a href="#/queue">Repository Queue (<%= queue %>)</a></div>',
            '</div>',
            '<div class="unified-panel-body" id="list_repositories">',
                '<div id="standard-search" style="height: 2em; margin: 1em;">',
                    '<span class="ui-widget" >',
                        '<input class="search-box-input" id="search_box" name="search" data-shedurl="<%= tool_shed.replace(/%2f/g, "/") %>" placeholder="Search repositories by name or id" size="60" type="text" />',
                    '</span>',
                '</div>',
                '<div style="clear: both; margin-top: 1em;">',
                    '<table class="grid">',
                        '<thead id="grid-table-header">',
                            '<tr>',
                                '<th style="width: 10%;">Owner</th>',
                                '<th style="width: 15%;">Name</th>',
                                '<th>Synopsis</th>',
                                '<th style="width: 10%;">Type</th>',
                            '</tr>',
                        '</thead>',
                        '<% _.each(category.get("repositories"), function(repository) { %>',
                            '<tr>',
                                '<td><%= repository.owner %></td>',
                                '<td>',
                                    '<div style="float: left; margin-left: 1px;" class="menubutton split">',
                                        '<a href="#/repository/s/<%= tool_shed %>/r/<%= repository.id %>"><%= repository.name %></a>',
                                    '</div>',
                                '</td>',
                                '<td><%= repository.description %></td>',
                                '<td><%= repository.type %></td>',
                            '</tr>',
                        '<% }); %>',
                    '</table>',
                '</div>',
            '</div>'
        ].join(''))
    });

    return {
        Category: ToolShedCategoryContentsView,
    };

});