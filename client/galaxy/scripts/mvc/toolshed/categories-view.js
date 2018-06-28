define(['mvc/toolshed/toolshed-model', 'mvc/toolshed/util'], function(toolshed_model, toolshed_util) {

    var ToolShedCategories = Backbone.View.extend({

        el: '#center',

        defaults: {
            tool_shed: "https://toolshed.g2.bx.psu.edu/"
        },

        initialize: function(options) {
            var self = this;
            var shed = options.tool_shed.replace(/\//g, '%2f');
            this.options = _.defaults(this.options || options, this.defaults);
            this.model = new toolshed_model.Categories();
            this.listenTo(this.model, 'sync', this.render);
            this.model.url = this.model.url + '?tool_shed_url=' + this.options.tool_shed;
            this.model.tool_shed = shed;
            this.model.fetch();
        },

        render: function(options) {
            this.options = _.extend(this.options, options);
            this.options.categories = this.model.models;
            this.options.queue = toolshed_util.queueLength();
            var category_list_template = this.templateCategoryList;
            this.$el.html(category_list_template(this.options));
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
                            console.log(data);
                            var result_list = toolshed_util.shedParser(data);
                            response(result_list);
                        });
                    },
                    minLength: 3,
                    select: function(event, ui) {
                        var tsr_id = ui.item.value;
                        var api_url = Galaxy.root + 'api/tool_shed/repository';
                        var params = {"tool_shed_url": that.model.tool_shed, "tsr_id": tsr_id};
                        var new_route = 'repository/s/' + that.model.tool_shed + '/r/' + tsr_id;
                        Backbone.history.navigate(new_route, {trigger: true, replace:true});
                    },
                });
            });
        },

        reDraw: function(options) {
            this.$el.empty();
            this.model.url = this.model.url + '?tool_shed_url=' + this.options.tool_shed;
            this.initialize(options);
        },

        templateCategoryList: _.template([
            '<style type="text/css">',
                '.ui-autocomplete { background-color: #fff; }',
                'li.ui-menu-item { list-style-type: none; }',
            '</style>',
            '<div class="unified-panel-header" id="panel_header" unselectable="on">',
                '<div class="unified-panel-header-inner" style="layout: inline;">Categories in <%= tool_shed.replace(/%2f/g, "/") %></div>',
                '<div class="unified-panel-header-inner" style="position: absolute; right: 5px; top: 0px;"><a href="#/queue">Repository Queue (<%= queue %>)</a></div>',
            '</div>',
            '<div class="unified-panel-body" id="list_categories">',
                '<div id="standard-search" style="height: 2em; margin: 1em;">',
                    '<span class="ui-widget" >',
                        '<input class="search-box-input" id="search_box" data-shedurl="<%= tool_shed.replace(/%2f/g, "/") %>" name="search" placeholder="Search repositories by name or id" size="60" type="text" />',
                    '</span>',
                '</div>',
                '<div style="clear: both; margin-top: 1em;">',
                    '<table class="grid">',
                        '<thead id="grid-table-header">',
                            '<tr>',
                                '<th>Name</th>',
                                '<th>Description</th>',
                                '<th>Repositories</th>',
                            '</tr>',
                        '</thead>',
                        '<% _.each(categories, function(category) { %>',
                            '<tr>',
                                '<td>',
                                    '<a href="#/category/s/<%= tool_shed %>/c/<%= category.get("id") %>"><%= category.get("name") %></a>',
                                '</td>',
                                '<td><%= category.get("description") %></td>',
                                '<td><%= category.get("repositories") %></td>',
                            '</tr>',
                        '<% }); %>',
                    '</table>',
                '</div>',
            '</div>',
        ].join(''))
    });

    return {
        CategoryView: ToolShedCategories,
    };

});