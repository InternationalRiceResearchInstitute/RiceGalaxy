define('mvc/workflow/workflow-globals', {});
define([
    'utils/utils',
    'mvc/workflow/workflow-globals',
    'mvc/workflow/workflow-manager',
    'mvc/workflow/workflow-canvas',
    'mvc/workflow/workflow-node',
    'mvc/workflow/workflow-icons',
    'mvc/workflow/workflow-forms',
    'mvc/ui/ui-misc',
    'utils/async-save-text',
    'libs/toastr',
    'ui/editable-text'
], function( Utils, Globals, Workflow, WorkflowCanvas, Node, WorkflowIcons, FormWrappers, Ui, async_save_text, Toastr ){

    // Reset tool search to start state.
    function reset_tool_search( initValue ) {
        // Function may be called in top frame or in tool_menu_frame;
        // in either case, get the tool menu frame.
        var tool_menu_frame = $("#galaxy_tools").contents();
        if (tool_menu_frame.length === 0) {
            tool_menu_frame = $(document);
            // Remove classes that indicate searching is active.
            $(this).removeClass("search_active");
            tool_menu_frame.find(".toolTitle").removeClass("search_match");

            // Reset visibility of tools and labels.
            tool_menu_frame.find(".toolSectionBody").hide();
            tool_menu_frame.find(".toolTitle").show();
            tool_menu_frame.find(".toolPanelLabel").show();
            tool_menu_frame.find(".toolSectionWrapper").each( function() {
                if ($(this).attr('id') !== 'recently_used_wrapper') {
                    // Default action.
                    $(this).show();
                } else if ($(this).hasClass("user_pref_visible")) {
                    $(this).show();
                }
            });
            tool_menu_frame.find("#search-no-results").hide();

            // Reset search input.
            tool_menu_frame.find("#search-spinner").hide();
            if (initValue) {
                var search_input = tool_menu_frame.find("#tool-search-query");
                search_input.val("search tools");
            }
        }
    }

    add_node_icon = function($to_el, nodeType) {
        var iconStyle = WorkflowIcons[nodeType];
        if(iconStyle) {
            var $icon = $('<i class="icon fa">&nbsp;</i>').addClass(iconStyle);
            $to_el.before($icon);
        }
    }

    // create form view
    return Backbone.View.extend({
        initialize: function(options) {
            var self = Globals.app = this;
            this.options = options;
            this.urls = options && options.urls || {};
            var close_editor = function() {
                self.workflow.check_changes_in_active_form();
                if ( workflow && self.workflow.has_changes ) {
                    var do_close = function() {
                        window.onbeforeunload = undefined;
                        window.document.location = self.urls.workflow_index;
                    };
                    window.show_modal( "Close workflow editor",
                                "There are unsaved changes to your workflow which will be lost.",
                                {
                                    "Cancel" : hide_modal,
                                    "Save Changes" : function() {
                                        save_current_workflow( null, do_close );
                                    }
                                }, {
                                    "Don't Save": do_close
                                } );
                } else {
                    window.document.location = self.urls.workflow_index;
                }
            };
            var save_current_workflow = function ( eventObj, success_callback ) {
                show_message( "Saving workflow", "progress" );
                self.workflow.check_changes_in_active_form();
                if (!self.workflow.has_changes) {
                    hide_modal();
                    if ( success_callback ) {
                        success_callback();
                    }
                    return;
                }
                self.workflow.rectify_workflow_outputs();
                Utils.request( {
                    url: Galaxy.root + 'api/workflows/' + self.options.id,
                    type: "PUT",
                    data: { workflow: self.workflow.to_simple() },
                    success: function( data ) {
                        var body = $( "<div/>" ).text( data.message );
                        if ( data.errors ) {
                            body.addClass( "warningmark" );
                            var errlist = $( "<ul/>" );
                            $.each( data.errors, function( i, v ) {
                                $( "<li/>" ).text( v ).appendTo( errlist );
                            });
                            body.append( errlist );
                        } else {
                            body.addClass( "donemark" );
                        }
                        self.workflow.name = data.name;
                        self.workflow.has_changes = false;
                        self.workflow.stored = true;
                        self.showWorkflowParameters();
                        if ( data.errors ) {
                            window.show_modal( "Saving workflow", body, { "Ok" : hide_modal } );
                        } else {
                            success_callback && success_callback();
                            hide_modal();
                        }
                    },
                    error: function( response ) {
                        window.show_modal( "Saving workflow failed.", response.err_msg, { "Ok" : hide_modal } );
                    }
                });
            };

            // Init searching.
            $("#tool-search-query").click( function (){
                $(this).focus();
                $(this).select();
            })
            .keyup( function () {
                // Remove italics.
                $(this).css("font-style", "normal");
                // Don't update if same value as last time
                if ( this.value.length < 3 ) {
                    reset_tool_search(false);
                } else if ( this.value != this.lastValue ) {
                    // Add class to denote that searching is active.
                    $(this).addClass("search_active");
                    // input.addClass(config.loadingClass);
                    // Add '*' to facilitate partial matching.
                    var q = this.value;
                    // Stop previous ajax-request
                    if (this.timer) {
                        clearTimeout(this.timer);
                    }
                    // Start a new ajax-request in X ms
                    $("#search-spinner").show();
                    this.timer = setTimeout(function () {
                        $.get(self.urls.tool_search, { q: q }, function (data) {
                            // input.removeClass(config.loadingClass);
                            // Show live-search if results and search-term aren't empty
                            $("#search-no-results").hide();
                            // Hide all tool sections.
                            $(".toolSectionWrapper").hide();
                            // This hides all tools but not workflows link (which is in a .toolTitle div).
                            $(".toolSectionWrapper").find(".toolTitle").hide();
                            if ( data.length != 0 ) {
                                // Map tool ids to element ids and join them.
                                var s = $.map( data, function( n, i ) { return "link-" + n; } );
                                // First pass to show matching tools and their parents.
                                $(s).each( function(index,id) {
                                    // Add class to denote match.
                                    $("[id='"+id+"']").parent().addClass("search_match");
                                    $("[id='"+id+"']").parent().show().parent().parent().show().parent().show();
                                });
                                // Hide labels that have no visible children.
                                $(".toolPanelLabel").each( function() {
                                   var this_label = $(this);
                                   var next = this_label.next();
                                   var no_visible_tools = true;
                                   // Look through tools following label and, if none are visible, hide label.
                                   while (next.length !== 0 && next.hasClass("toolTitle")) {
                                       if (next.is(":visible")) {
                                           no_visible_tools = false;
                                           break;
                                       } else {
                                           next = next.next();
                                       }
                                    }
                                    if (no_visible_tools) {
                                        this_label.hide();
                                    }
                                });
                            } else {
                                $("#search-no-results").show();
                            }
                            $("#search-spinner").hide();
                        }, "json" );
                    }, 400 );
                }
                this.lastValue = this.value;
            });

            // Canvas overview management
            this.canvas_manager = Globals.canvas_manager = new WorkflowCanvas( this, $("#canvas-viewport"), $("#overview") );

            // Initialize workflow state
            this.reset();

            // get available datatypes for post job action options
            this.datatypes = JSON.parse($.ajax({
                url     : Galaxy.root + 'api/datatypes',
                async   : false
            }).responseText);

            // get datatype mapping options
            this.datatypes_mapping = JSON.parse($.ajax({
                url     : Galaxy.root + 'api/datatypes/mapping',
                async   : false
            }).responseText);

            // set mapping sub lists
            this.ext_to_type = this.datatypes_mapping.ext_to_class_name;
            this.type_to_type = this.datatypes_mapping.class_to_classes;

            // Load workflow definition
            this._workflowLoadAjax(self.options.id, {
                success: function( data ) {
                     self.reset();
                     self.workflow.from_simple( data, true );
                     self.workflow.has_changes = false;
                     self.workflow.fit_canvas_to_nodes();
                     self.scroll_to_nodes();
                     self.canvas_manager.draw_overview();
                     // Determine if any parameters were 'upgraded' and provide message
                     var upgrade_message = "";
                     _.each( data.steps, function( step, step_id ) {
                        var details = "";
                        if ( step.errors ) {
                            details += "<li>" + step.errors + "</li>";
                        }
                        _.each( data.upgrade_messages[ step_id ], function( m ) {
                            details += "<li>" + m + "</li>";
                        });
                        if ( details ) {
                            upgrade_message += "<li>Step " + ( parseInt( step_id, 10 ) + 1 ) + ": " + self.workflow.nodes[ step_id ].name + "<ul>" + details + "</ul></li>";
                        }
                     });
                     if ( upgrade_message ) {
                        window.show_modal( "Issues loading this workflow", "Please review the following issues, possibly resulting from tool upgrades or changes.<p><ul>" + upgrade_message + "</ul></p>", { "Continue" : hide_modal } );
                     } else {
                        hide_modal();
                     }
                     self.showWorkflowParameters();
                 },
                 beforeSubmit: function( data ) {
                     show_message( "Loading workflow", "progress" );
                 }
            });

            window.make_popupmenu && make_popupmenu( $("#workflow-options-button"), {
                "Save" : save_current_workflow,
                "Save As": workflow_save_as,
                "Run": function() {
                    window.location = Galaxy.root + "workflow/run?id=" + self.options.id;
                },
                "Edit Attributes" : function() { self.workflow.clear_active_node() },
                "Auto Re-layout": layout_editor,
                "Close": close_editor
            });

            /******************************************** Issue 3000*/
            function workflow_save_as() {
                var body = $('<form><label style="display:inline-block; width: 100%;">Save as name: </label><input type="text" id="workflow_rename" style="width: 80%;" autofocus/>' + 
                '<br><label style="display:inline-block; width: 100%;">Annotation: </label><input type="text" id="wf_annotation" style="width: 80%;" /></form>');
                    window.show_modal("Save As a New Workflow", body, {
                        "OK": function () {
                            var rename_name = $('#workflow_rename').val().length > 0 ? $('#workflow_rename').val() : "SavedAs_" + self.workflow.name;
                            var rename_annotation = $('#wf_annotation').val().length > 0 ? $('#wf_annotation').val() : "";
                            $.ajax({
                                url: self.urls.workflow_save_as,
                                type: "POST",
                                data: {
                                    workflow_name: rename_name,
                                    workflow_annotation: rename_annotation,
                                    workflow_data: function() { return JSON.stringify( self.workflow.to_simple() ); }
                                }
                            }).done(function(id){
                                window.onbeforeunload = undefined;
                                window.location = Galaxy.root + "workflow/editor?id=" + id;
                                hide_modal();
                            }).fail(function(){
                                hide_modal();
                                alert("Saving this workflow failed. Please contact this site's administrator.");
                            });
                        },
                        "Cancel": hide_modal
                    });
            };

            function edit_workflow_outputs(){
                self.workflow.clear_active_node();
                $('.right-content').hide();
                var new_content = "";
                for (var node_key in self.workflow.nodes){
                    var node = self.workflow.nodes[node_key];
                    if(['tool', 'subworkflow'].indexOf(node.type) >= 0){
                        new_content += "<div class='toolForm' style='margin-bottom:5px;'><div class='toolFormTitle'>Step " + node.id + " - " + node.name + "</div>";
                        for (var ot_key in node.output_terminals){
                            var output = node.output_terminals[ot_key];
                            if (node.isWorkflowOutput(output.name)) {
                                new_content += "<p>"+output.name +"<input type='checkbox' name='"+ node.id + "|" + output.name +"' checked /></p>";
                            }
                            else{
                                new_content += "<p>"+output.name +"<input type='checkbox' name='"+ node.id + "|" + output.name +"' /></p>";
                            }
                        }
                        new_content += "</div>";
                    }
                }
                $("#output-fill-area").html(new_content);
                $("#output-fill-area input").bind('click', function(){
                    var node_id = this.name.split('|')[0];
                    var workflowNode = this.workflow.nodes[node_id];
                    var output_name = this.name.split('|')[1];
                    if (this.checked){
                        workflowNode.addWorkflowOutput(output_name);
                    }else{
                        workflowNode.removeWorkflowOutput(output_name);
                    }
                    self.workflow.has_changes = true;
                });
                $('#workflow-output-area').show();
            }

            function layout_editor() {
                self.workflow.layout();
                self.workflow.fit_canvas_to_nodes();
                self.scroll_to_nodes();
                self.canvas_manager.draw_overview();
            }

            // On load, set the size to the pref stored in local storage if it exists
            var overview_size = $.jStorage.get("overview-size");
            if (overview_size !== undefined) {
                $("#overview-border").css( {
                    width: overview_size,
                    height: overview_size
                });
            }

            // Show viewport on load unless pref says it's off
            if ($.jStorage.get("overview-off")) {
                hide_overview();
            } else {
                show_overview();
            }

            // Stores the size of the overview into local storage when it's resized
            $("#overview-border").bind( "dragend", function( e, d ) {
                var op = $(this).offsetParent();
                var opo = op.offset();
                var new_size = Math.max( op.width() - ( d.offsetX - opo.left ),
                                         op.height() - ( d.offsetY - opo.top ) );
                $.jStorage.set("overview-size", new_size + "px");
            });

            function show_overview() {
                $.jStorage.set("overview-off", false);
                $("#overview-border").css("right", "0px");
                $("#close-viewport").css("background-position", "0px 0px");
            }

            function hide_overview() {
                $.jStorage.set("overview-off", true);
                $("#overview-border").css("right", "20000px");
                $("#close-viewport").css("background-position", "12px 0px");
            }

            // Lets the overview be toggled visible and invisible, adjusting the arrows accordingly
            $("#close-viewport").click( function() {
                if ( $("#overview-border").css("right") === "0px" ) {
                    hide_overview();
                } else {
                    show_overview();
                }
            });

            // Unload handler
            window.onbeforeunload = function() {
                if ( workflow && self.workflow.has_changes ) {
                    return "There are unsaved changes to your workflow which will be lost.";
                }
            };

            this.options.workflows.length > 0 && $( "#left" ).find( ".toolMenu" ).append( this._buildToolPanelWorkflows() );

            // Tool menu
            $( "div.toolSectionBody" ).hide();
            $( "div.toolSectionTitle > span" ).wrap( "<a href='#'></a>" );
            var last_expanded = null;
            $( "div.toolSectionTitle" ).each( function() {
               var body = $(this).next( "div.toolSectionBody" );
               $(this).click( function() {
                   if ( body.is( ":hidden" ) ) {
                       if ( last_expanded ) last_expanded.slideUp( "fast" );
                       last_expanded = body;
                       body.slideDown( "fast" );
                   }
                   else {
                       body.slideUp( "fast" );
                       last_expanded = null;
                   }
               });
            });

            // Rename async.
            async_save_text("workflow-name", "workflow-name", self.urls.rename_async, "new_name");

            // Tag async. Simply have the workflow edit element generate a click on the tag element to activate tagging.
            $('#workflow-tag').click( function() {
                $('.tag-area').click();
                return false;
            });
            // Annotate async.
            async_save_text("workflow-annotation", "workflow-annotation", self.urls.annotate_async, "new_annotation", 25, true, 4);
        },

        _buildToolPanelWorkflows: function() {
            var self = this;
            var $section = $(   '<div class="toolSectionWrapper">' +
                                    '<div class="toolSectionTitle">' +
                                        '<a href="#"><span>Workflows</span></a>' +
                                    '</div>' +
                                    '<div class="toolSectionBody">' +
                                        '<div class="toolSectionBg"/>' +
                                    '</div>' +
                                '</div>' );
            _.each( this.options.workflows, function( workflow ) {
                if( workflow.id !== self.options.id ) {
                    var copy = new Ui.ButtonIcon({
                        icon        : 'fa fa-copy',
                        cls         : 'ui-button-icon-plain',
                        tooltip     : 'Copy and insert individual steps',
                        onclick     : function() {
                            if( workflow.step_count < 2 ) {
                                self.copy_into_workflow( workflow.id, workflow.name );
                            } else {
                                // don't ruin the workflow by adding 50 steps unprompted.
                                Galaxy.modal.show({
                                    title   : 'Warning',
                                    body    : 'This will copy ' + workflow.step_count + ' new steps into your workflow.',
                                    buttons : {
                                        'Cancel' : function() { Galaxy.modal.hide(); },
                                        'Copy'   : function() { Galaxy.modal.hide(); self.copy_into_workflow( workflow.id, workflow.name ); }
                                    }
                                });
                            }
                        }
                    });
                    var $add = $( '<a/>' ).attr( 'href', '#' ).html( workflow.name ).on( 'click', function() {
                        self.add_node_for_subworkflow( workflow.latest_id, workflow.name );
                    });
                    $section.find( '.toolSectionBg' ).append( $( '<div/>' ).addClass( 'toolTitle' ).append( $add ).append( copy.$el ) );
                }
            });
            return $section;
        },

        copy_into_workflow: function(workflowId) {
            // Load workflow definition
            var self = this;
            this._workflowLoadAjax(workflowId, {
                success: function( data ) {
                    self.workflow.from_simple( data, false );
                    // Determine if any parameters were 'upgraded' and provide message
                    var upgrade_message = "";
                    $.each( data.upgrade_messages, function( k, v ) {
                       upgrade_message += ( "<li>Step " + ( parseInt(k, 10) + 1 ) + ": " + self.workflow.nodes[k].name + "<ul>");
                       $.each( v, function( i, vv ) {
                           upgrade_message += "<li>" + vv +"</li>";
                       });
                       upgrade_message += "</ul></li>";
                    });
                    if ( upgrade_message ) {
                       window.show_modal( "Subworkflow embedded with changes",
                                   "Problems were encountered loading this workflow (possibly a result of tool upgrades). Please review the following parameters and then save.<ul>" + upgrade_message + "</ul>",
                                   { "Continue" : hide_modal } );
                    } else {
                       hide_modal();
                    }
                },
                beforeSubmit: function( data ) {
                   show_message( "Importing workflow", "progress" );
                }
            });
        },

        // Global state for the whole workflow
        reset: function() {
            this.workflow && this.workflow.remove_all();
            this.workflow = Globals.workflow = new Workflow( this, $("#canvas-container") );
        },

        scroll_to_nodes: function () {
            var cv = $("#canvas-viewport");
            var cc = $("#canvas-container");
            var top, left;
            if ( cc.width() < cv.width() ) {
                left = ( cv.width() - cc.width() ) / 2;
            } else {
                left = 0;
            }
            if ( cc.height() < cv.height() ) {
                top = ( cv.height() - cc.height() ) / 2;
            } else {
                top = 0;
            }
            cc.css( { left: left, top: top } );
        },

        _workflowLoadAjax: function(workflowId, options) {
            $.ajax(Utils.merge(options, {
                url: this.urls.load_workflow,
                data: { id: workflowId, "_": "true" },
                dataType: 'json',
                cache: false
            }));
        },

        _moduleInitAjax: function(node, request_data) {
            var self = this;
            Utils.request({
                type    : 'POST',
                url     : Galaxy.root + 'api/workflows/build_module',
                data    : request_data,
                success : function( data ) {
                    node.init_field_data( data );
                    node.update_field_data( data );
                    self.workflow.activate_node( node );
                }
            });
        },

        // Add a new step to the workflow by tool id
        add_node_for_tool: function ( id, title ) {
            var node = this.workflow.create_node( 'tool', title, id );
            this._moduleInitAjax(node, { type: "tool", tool_id: id, "_": "true" });
        },

        // Add a new step to the workflow by tool id
        add_node_for_subworkflow: function ( id, title ) {
            var node = this.workflow.create_node( 'subworkflow', title, id );
            this._moduleInitAjax(node, { type: "subworkflow", content_id: id, "_": "true" });
        },

        add_node_for_module: function ( type, title ) {
            var node = this.workflow.create_node( type, title );
            this._moduleInitAjax(node, { type: type, "_": "true" });
        },

        // This function preloads how to display known pja's.
        display_pja: function (pja, node) {
            // DBTODO SANITIZE INPUTS.
            var self = this;
            $("#pja_container").append( get_pja_form(pja, node) );
            $("#pja_container>.toolForm:last>.toolFormTitle>.buttons").click(function (){
                var action_to_rem = $(this).closest(".toolForm", ".action_tag").children(".action_tag:first").text();
                $(this).closest(".toolForm").remove();
                delete self.workflow.active_node.post_job_actions[action_to_rem];
                self.workflow.active_form_has_changes = true;
            });
        },

        display_pja_list: function (){
            return pja_list;
        },

        display_file_list: function (node){
            var addlist = "<select id='node_data_list' name='node_data_list'>";
            for (var out_terminal in node.output_terminals){
                addlist += "<option value='" + out_terminal + "'>"+ out_terminal +"</option>";
            }
            addlist += "</select>";
            return addlist;
        },

        new_pja: function (action_type, target, node){
            if (node.post_job_actions === undefined){
                //New tool node, set up dict.
                node.post_job_actions = {};
            }
            if (node.post_job_actions[action_type+target] === undefined) {
                var new_pja = {};
                new_pja.action_type = action_type;
                new_pja.output_name = target;
                node.post_job_actions[action_type+target] = null;
                node.post_job_actions[action_type+target] =  new_pja;
                display_pja(new_pja, node);
                this.workflow.active_form_has_changes = true;
                return true;
            } else {
                return false;
            }
        },

        showWorkflowParameters: function () {
            var parameter_re = /\$\{.+?\}/g;
            var workflow_parameters = [];
            var wf_parm_container = $( '#workflow-parameters-container' );
            var wf_parm_box = $( '#workflow-parameters-box' );
            var new_parameter_content = '';
            var matches = [];
            $.each(this.workflow.nodes, function ( k, node ){
                if ( node.config_form && node.config_form.inputs ) {
                    Utils.deepeach( node.config_form.inputs, function( d ) {
                        if ( typeof d.value == 'string' ) {
                            var form_matches = d.value.match( parameter_re );
                            if ( form_matches ) {
                                matches = matches.concat( form_matches );
                            }
                        }
                    });
                }
                if (node.post_job_actions){
                    $.each(node.post_job_actions, function(k, pja){
                        if (pja.action_arguments){
                            $.each(pja.action_arguments, function(k, action_argument){
                                var arg_matches = action_argument.match(parameter_re);
                                if (arg_matches){
                                    matches = matches.concat(arg_matches);
                                }
                            });
                        }
                    });
                }
                if (matches){
                    $.each(matches, function(k, element){
                        if ($.inArray(element, workflow_parameters) === -1){
                            workflow_parameters.push(element);
                        }
                    });
                }
            });
            if (workflow_parameters && workflow_parameters.length !== 0){
                $.each(workflow_parameters, function(k, element){
                    new_parameter_content += "<div>" + element.substring(2, element.length -1) + "</div>";
                });
                wf_parm_container.html(new_parameter_content);
                wf_parm_box.show();
            }else{
                wf_parm_container.html(new_parameter_content);
                wf_parm_box.hide();
            }
        },

        showAttributes: function() {
            $( '.right-content' ).hide();
            $( '#edit-attributes' ).show();
        },

        showForm: function ( content, node ) {
            var self = this;
            var cls = 'right-content';
            var id  = cls + '-' + node.id;
            var $container = $( '#' + cls );
            if ( content && $container.find( '#' + id ).length == 0 ) {
                var $el = $( '<div id="' + id + '" class="' + cls + '"/>' );
                content.node = node;
                content.workflow = this.workflow;
                content.datatypes = this.datatypes;
                content.icon = WorkflowIcons[ node.type ];
                content.cls = 'ui-portlet-narrow';
                if ( node ) {
                    var form_type = ( node.type == 'tool' ? 'Tool' : 'Default' );
                    $el.append( ( new FormWrappers[ form_type ]( content ) ).form.$el );
                    $container.append( $el );
                } else {
                    Galaxy.emit.debug('workflow-view::initialize()', 'Node not found in workflow.');
                }
            }
            $( '.' + cls ).hide();
            $container.find( '#' + id ).show();
            $container.show();
            $container.scrollTop();
        },

        isSubType: function ( child, parent ) {
            child = this.ext_to_type[child];
            parent = this.ext_to_type[parent];
            return ( this.type_to_type[child] ) && ( parent in this.type_to_type[child] );
        },

        prebuildNode: function ( type, title_text, content_id ) {
            var self = this;
            var $f = $("<div class='toolForm toolFormInCanvas'/>");
            var $title = $("<div class='toolFormTitle unselectable'><span class='nodeTitle'>" + title_text + "</div></div>" );
            add_node_icon($title.find('.nodeTitle'), type);
            $f.append( $title );
            $f.css( "left", $(window).scrollLeft() + 20 );
            $f.css( "top", $(window).scrollTop() + 20 );
            $f.append($("<div class='toolFormBody'></div>"));
            var node = new Node( this, { element: $f } );
            node.type = type;
            node.content_id = content_id;
            var tmp = "<div><img height='16' align='middle' src='" + Galaxy.root + "static/images/loading_small_white_bg.gif'/> loading tool info...</div>";
            $f.find(".toolFormBody").append(tmp);
            // Fix width to computed width
            // Now add floats
            var buttons = $("<div class='buttons' style='float: right;'></div>");
            buttons.append( $("<div/>").addClass("fa-icon-button fa fa-times").click( function( e ) {
                node.destroy();
            }));
            // Place inside container
            $f.appendTo( "#canvas-container" );
            // Position in container
            var o = $("#canvas-container").position();
            var p = $("#canvas-container").parent();
            var width = $f.width();
            var height = $f.height();
            $f.css( { left: ( - o.left ) + ( p.width() / 2 ) - ( width / 2 ), top: ( - o.top ) + ( p.height() / 2 ) - ( height / 2 ) } );
            buttons.prependTo( $f.find(".toolFormTitle" ) );
            width += ( buttons.width() + 10 );
            $f.css( "width", width );
            $f.bind( "dragstart", function() {
                self.workflow.activate_node( node );
            }).bind( "dragend", function() {
                self.workflow.node_changed( this );
                self.workflow.fit_canvas_to_nodes();
                self.canvas_manager.draw_overview();
            }).bind( "dragclickonly", function() {
                self.workflow.activate_node( node );
            }).bind( "drag", function( e, d ) {
                // Move
                var po = $(this).offsetParent().offset(),
                    x = d.offsetX - po.left,
                    y = d.offsetY - po.top;
                $(this).css( { left: x, top: y } );
                // Redraw
                $(this).find( ".terminal" ).each( function() {
                    this.terminal.redraw();
                });
            });
            return node;
        }
    });
});
