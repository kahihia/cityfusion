;(function($, window, document, undefined) {

    'use strict';

    var EventPage = function(){        
        this.initEventActions();
        $("a#photoFancy").fancybox({
            'hideOnContentClick': true
        });
    };

    EventPage.prototype = {
        initEventActions: function(){
            this.eventActions = new window.EventActions($(".event-details"));
        }
    };

    $(window).load(function(){
        window.eventPage = new EventPage();
    });

})(jQuery, window, document);