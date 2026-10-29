#import "DropSession.h"
#import "PythonEngine.h"
#import <BackgroundTasks/BackgroundTasks.h>

static NSString *const TaskID = @"com.thunderboldx.nyxor.drop.session";
static NSDictionary *Query(NSDictionary *query) {
    NSData *data = [NSJSONSerialization dataWithJSONObject:query options:0 error:nil];
    NSString *reply = [PythonEngine request:[[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding]];
    return [NSJSONSerialization JSONObjectWithData:[reply dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil] ?: @{@"ok":@NO};
}

@interface DropSession ()
@property(nonatomic, strong) dispatch_queue_t queue;
@property(nonatomic, strong) dispatch_source_t timer;
@property(nonatomic, strong) BGContinuedProcessingTask *task;
@property(nonatomic, copy) NSString *identity;
@property(nonatomic, copy) NSString *code;
@property(nonatomic, copy) NSDictionary *goal;
@property BOOL registered;
@property BOOL preparing;
@property BOOL polling;
@property NSUInteger generation;
@property int64_t lastUnits;
@end

@implementation DropSession
- (instancetype)initWithQueue:(dispatch_queue_t)queue {
    if ((self = [super init])) {
        self.queue = queue;
        self.code = @"idle";
        __weak DropSession *weak = self;
        self.registered = [BGTaskScheduler.sharedScheduler registerForTaskWithIdentifier:TaskID usingQueue:dispatch_get_main_queue() launchHandler:^(__kindof BGTask *task) {
            DropSession *owner = weak;
            if (!owner || !owner.identity || ![task isKindOfClass:BGContinuedProcessingTask.class]) {
                [task setTaskCompletedWithSuccess:NO]; return;
            }
            owner.task = (BGContinuedProcessingTask *)task;
            owner.lastUnits = -1;
            owner.code = @"active";
            NSUInteger generation = owner.generation;
            NSString *identity = owner.identity;
            task.expirationHandler = ^{dispatch_async(dispatch_get_main_queue(), ^{
                if (owner.generation == generation) [owner finish:NO stop:YES code:@"expired"];
            });};
            dispatch_async(owner.queue, ^{
                NSDictionary *reply = Query(@{@"action":@"ios_grant",@"id":identity});
                dispatch_async(dispatch_get_main_queue(), ^{
                    if (owner.generation != generation) return;
                    if (![reply[@"ok"] boolValue]) {[owner finish:NO stop:YES code:@"stopped"]; return;}
                    [owner startPolling];
                });
            });
        }];
    }
    return self;
}
- (NSDictionary *)status {
    return @{@"available":@(self.registered),@"active":@(self.identity != nil || self.preparing),@"code":self.code ?: @"idle",@"goal":self.goal ?: @{}};
}
- (void)begin:(NSString *)drop completion:(void (^)(NSDictionary *))completion {
    if (!self.registered || self.identity || self.preparing) {
        completion(@{@"ok":@NO,@"error":@"Background session is unavailable or already running"}); return;
    }
    self.preparing = YES;
    NSUInteger generation = ++self.generation;
    dispatch_async(self.queue, ^{
        NSDictionary *reply = Query(@{@"action":@"ios_plan",@"drop_id":drop});
        dispatch_async(dispatch_get_main_queue(), ^{
            self.preparing = NO;
            NSString *identity = reply[@"data"][@"id"];
            if (self.generation != generation || UIApplication.sharedApplication.applicationState != UIApplicationStateActive) {
                if (identity) dispatch_async(self.queue, ^{Query(@{@"action":@"ios_finish",@"id":identity,@"stop":@NO});});
                completion(@{@"ok":@NO,@"error":@"Return to NYXOR and try again"}); return;
            }
            if (![reply[@"ok"] boolValue] || ![identity isKindOfClass:NSString.class]) {completion(reply); return;}
            self.identity = identity;
            NSDictionary *goal = reply[@"data"];
            self.goal = @{@"title":goal[@"title"] ?: @"",@"account":goal[@"account"] ?: @"",@"game":goal[@"game"] ?: @""};
            NSString *title = [NSString stringWithFormat:@"NYXOR · %@",goal[@"game"] ?: @"Twitch Drops"];
            BGContinuedProcessingTaskRequest *request = [[BGContinuedProcessingTaskRequest alloc] initWithIdentifier:TaskID title:title subtitle:goal[@"title"] ?: @"Twitch Drop"];
            request.strategy = BGContinuedProcessingTaskRequestSubmissionStrategyFail;
            NSError *error = nil;
            if (![BGTaskScheduler.sharedScheduler submitTaskRequest:request error:&error]) {
                [self finish:NO stop:NO code:@"foreground_only"];
                completion(@{@"ok":@NO,@"error":@"iOS did not grant background time. Foreground farming is still available."});
            } else completion(@{@"ok":@YES,@"data":@{}});
        });
    });
}
- (void)startPolling {
    self.timer = dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0, dispatch_get_main_queue());
    dispatch_source_set_timer(self.timer, DISPATCH_TIME_NOW, 15 * NSEC_PER_SEC, NSEC_PER_SEC);
    __weak DropSession *weak = self;
    dispatch_source_set_event_handler(self.timer, ^{[weak poll];});
    dispatch_resume(self.timer);
}
- (void)poll {
    if (!self.identity || self.polling) return;
    self.polling = YES;
    NSString *identity = self.identity;
    NSUInteger generation = self.generation;
    dispatch_async(self.queue, ^{
        NSDictionary *reply = Query(@{@"action":@"ios_poll",@"id":identity});
        dispatch_async(dispatch_get_main_queue(), ^{
            if (self.generation != generation) return;
            self.polling = NO;
            if (![reply[@"ok"] boolValue]) {[self finish:NO stop:YES code:@"stopped"]; return;}
            NSDictionary *goal = reply[@"data"];
            int64_t units = [goal[@"units"] longLongValue];
            if (self.lastUnits != units) {
                self.lastUnits = units;
                self.task.progress.totalUnitCount = [goal[@"total"] longLongValue];
                self.task.progress.completedUnitCount = units;
                NSString *title = [NSString stringWithFormat:@"NYXOR · %@",goal[@"game"] ?: @"Twitch Drops"];
                NSString *subtitle = [NSString stringWithFormat:@"%@ · %@ / %@ min",goal[@"title"],goal[@"current"],goal[@"required"]];
                [self.task updateTitle:title subtitle:subtitle];
            }
            if ([goal[@"status"] isEqual:@"completed"]) [self finish:YES stop:YES code:@"completed"];
            else if ([@[@"unavailable",@"stopped"] containsObject:goal[@"status"]]) [self finish:NO stop:YES code:goal[@"status"]];
        });
    });
}
- (void)finish:(BOOL)success stop:(BOOL)stop code:(NSString *)code {
    NSString *identity = self.identity;
    BGContinuedProcessingTask *task = self.task;
    self.identity = nil; self.task = nil; self.code = code;
    self.generation++; self.preparing = NO; self.polling = NO;
    if (self.timer) {dispatch_source_cancel(self.timer); self.timer = nil;}
    [BGTaskScheduler.sharedScheduler cancelTaskRequestWithIdentifier:TaskID];
    if (task) task.expirationHandler = nil;
    if (!identity && !task) return;
    // Stop/save before releasing the processing task; use a bounded cleanup
    // lease in case iOS is expiring the longer session at this moment.
    __block UIBackgroundTaskIdentifier lease = UIBackgroundTaskInvalid;
    __block BOOL finished = NO;
    void (^finishCleanup)(void) = ^{
        if (finished) return;
        finished = YES;
        if (task) [task setTaskCompletedWithSuccess:success];
        if (lease != UIBackgroundTaskInvalid) {
            [UIApplication.sharedApplication endBackgroundTask:lease];
            lease = UIBackgroundTaskInvalid;
        }
    };
    lease = [UIApplication.sharedApplication beginBackgroundTaskWithName:@"Save NYXOR session" expirationHandler:finishCleanup];
    dispatch_async(self.queue, ^{
        if (identity) Query(@{@"action":@"ios_finish",@"id":identity,@"stop":@(stop)});
        dispatch_async(dispatch_get_main_queue(), finishCleanup);
    });
}
- (void)cancel {[self finish:NO stop:YES code:@"cancelled"];}
@end
