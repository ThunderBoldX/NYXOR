#import <UIKit/UIKit.h>

@interface DropSession : NSObject
- (instancetype)initWithQueue:(dispatch_queue_t)queue;
- (void)begin:(NSString *)drop completion:(void (^)(NSDictionary *))completion;
- (void)cancel;
- (NSDictionary *)status;
@end
