define([
    "mvc/list/list-view",
    "mvc/dataset/dataset-li",
    "mvc/base-mvc",
    "utils/localization"
], function( LIST_VIEW, DATASET_LI, BASE_MVC, _l ){
'use strict';

var logNamespace = 'dataset';
/* =============================================================================
TODO:

============================================================================= */
var _super = LIST_VIEW.ListPanel;
/** @class  non-editable, read-only View/Controller for a list of datasets.
 */
var DatasetList = _super.extend(
/** @lends DatasetList.prototype */{
    _logNamespace : logNamespace,

    /** class to use for constructing the sub-views */
    viewClass       : DATASET_LI.DatasetListItemView,
    className       : _super.prototype.className + ' dataset-list',

    /** string to no hdas match the search terms */
    noneFoundMsg    : _l( 'No matching datasets found' ),

    // ......................................................................... SET UP
    /** Set up the view, set up storage, bind listeners to HistoryContents events
     *  @param {Object} attributes optional settings for the panel
     */
    initialize : function( attributes ){
        _super.prototype.initialize.call( this, attributes );
    },

    /** Return a string rep of the history */
    toString : function(){
        return 'DatasetList(' + this.collection + ')';
    }
});

//==============================================================================
    return {
        DatasetList : DatasetList
    };
});
