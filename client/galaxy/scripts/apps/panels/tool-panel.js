var Tools = require( 'mvc/tool/tools' ),
    Upload = require( 'mvc/upload/upload-view' ),
    _l = require( 'utils/localization' ),
    ToolForm = require( 'mvc/tool/tool-form-composite' );

var ToolPanel = Backbone.View.extend({
    initialize: function( page, options ) {
        // access configuration options
        var config = options.config;
        this.root  = options.root;

        /** @type {Object[]} descriptions of user's workflows to be shown in the tool menu */
        this.stored_workflow_menu_entries = config.stored_workflow_menu_entries || [];

        // create tool search, tool panel, and tool panel view.
        var tool_search = new Tools.ToolSearch({
            hidden      : false
        });
        var tools = new Tools.ToolCollection( config.toolbox );
        this.tool_panel = new Tools.ToolPanel({
            tool_search : tool_search,
            tools       : tools,
            layout      : config.toolbox_in_panel
        });
        this.tool_panel_view = new Tools.ToolPanelView({ model: this.tool_panel });

        // add upload modal
        this.upload_button = new Upload({
            nginx_upload_path   : config.nginx_upload_path,
            ftp_upload_site     : config.ftp_upload_site,
            default_genome      : config.default_genome,
            default_extension   : config.default_extension,
        });

        // add uploader button to Galaxy object
        Galaxy.upload = this.upload_button;

        // components for panel definition
        this.model = new Backbone.Model({
            title   : _l( 'Tools' ),
            buttons : [ this.upload_button ]
        });

        // build body template
        this.setElement( this._template() );
    },

    render : function(){
        // if there are tools, render panel and display everything
        var self = this;
        if ( this.tool_panel.get( 'layout' ).size() > 0 ) {
            this.$el.prepend( this.tool_panel_view.$el );
            this.tool_panel_view.render();
        }
        // build the dom for the workflow portion of the tool menu
        // add internal workflow list
        self.$( '#internal-workflows' ).append( self._templateAllWorkflow({
            title   : _l( 'All workflows' ),
            href    : 'workflow'
        }));
        _.each( this.stored_workflow_menu_entries, function( menu_entry ){
            self.$( '#internal-workflows' ).append( self._templateWorkflowLink({
                title : menu_entry.stored_workflow.name,
                href  : 'workflow/run?id=' + menu_entry.encoded_stored_workflow_id
            }));
        });
    },

    /** build a link to one tool */
    _templateTool: function( tool ) {
        return [
            '<div class="toolTitle">',
                '<a href="', this.root, tool.href, '" target="galaxy_main">', tool.title, '</a>',
            '</div>'
        ].join('');
    },

    /** build a link to 'All Workflows' */
    _templateAllWorkflow: function( tool ) {
        return [
            '<div class="toolTitle">',
                // global
                '<a href="', Galaxy.root, tool.href, '">', tool.title, '</a>',
            '</div>'
        ].join('');
    },

    /** build links to workflows in toolpanel */
    _templateWorkflowLink: function( wf ) {
        return [
            '<div class="toolTitle">',
                '<a class="'+ wf.cls +' " href="', Galaxy.root, wf.href, '">', wf.title, '</a>',
            '</div>'
        ].join('');
    },

    /** override to include inital menu dom and workflow section */
    _template : function() {
        return [
            '<div class="toolMenuContainer">',
                '<div class="toolMenu" style="display: none">',
                    '<div id="search-no-results" style="display: none; padding-top: 5px">',
                        '<em><strong>', _l( 'Search did not match any tools.' ), '</strong></em>',
                    '</div>',
                '</div>',
                '<div class="toolSectionPad"/>',
                '<div class="toolSectionPad"/>',
                '<div class="toolSectionTitle" id="title_XXinternalXXworkflow">',
                    '<span>', _l( 'Workflows' ), '</span>',
                '</div>',
                '<div id="internal-workflows" class="toolSectionBody">',
                    '<div class="toolSectionBg"/>',
                '</div>',
            '</div>'
        ].join('');
    },

    toString : function() { return 'toolPanel' }
});

module.exports = ToolPanel;
