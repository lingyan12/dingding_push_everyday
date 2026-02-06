## 使用  钉钉群聊中自定义机器人，给群推送消息的项目



### log/： 运行时生成的 日志

### config/： 里面存放配置文件

image.txt ，此处存放图片的url，每次运行会 读取并删除首行url（类似于pop），注意有些域名会被dingding屏蔽

config.json:存放一个json形式的运行配置。其中的webhook、secret，需要自己再钉钉群自己申请一个机器人，并将其webhook、secret填写如config.json配置文件中。申请实例如下

### 注：本脚本已经设置了 自动 cd切换到 当前py文件目录下，故可直接设置为windows定时任务。



---



### 使用步骤如下：

![image-20260206112457027](./assets/6.png)













---






## 1.

![image-20260206110016084](./assets/1.png)

### 2

![image-20260206110128491](./assets/image-20260206110128491.png)

### 3

![image-20260206110151842](./assets/image-20260206110151842.png)

### 4

![image-20260206110241612](./assets/image-20260206110241612.png)
